"""
AI processing step for the processing pipeline.

Handles AI processing and JSON parsing.
"""
import os
import asyncio
from typing import Tuple

from services.ai_service import process_drawing
from utils.json_utils import parse_json_safely
from config.settings import get_enable_metadata_repair
from processing.pipeline.types import ProcessingState, ProcessingStatus
from processing.pipeline.services import PipelineServices


async def step_ai_processing_and_parsing(
    state: ProcessingState,
    services: PipelineServices,
    pdf_path: str,
    file_name: str,
    pipeline_id: str,
    error_output_path: str,
) -> Tuple[ProcessingState, bool]:
    """
    Process extracted content with AI and parse the response.
    
    This step:
    1. Gets raw content from extraction result
    2. Processes with AI using appropriate drawing type
    3. Parses and validates the JSON response
    4. Updates the processing state with results
    
    Note: Mutates state in place.
    
    Args:
        state: Processing state (mutated in place)
        services: Pipeline services bundle
        pdf_path: Path to the PDF file
        file_name: Name of the PDF file
        pipeline_id: Unique pipeline identifier
        error_output_path: Path for error status files
        
    Returns:
        Tuple of (state, success) where success indicates processing succeeded
    """
    logger = services["logger"]
    
    extraction_result = state["extraction_result"]
    if not extraction_result or not extraction_result.success:
        logger.error(f"Extraction failed for {file_name}")
        return state, False

    raw_content = extraction_result.raw_text
    processing_type = state["processing_type_for_ai"]

    # Add tables to raw content
    for table in extraction_result.tables:
        raw_content += f"\nTABLE:\n{table['content']}\n"

    # Process with AI
    mech_second_pass = os.getenv("MECH_SECOND_PASS", "true").lower() == "true"
    max_attempts = 2 if ("mechanical" in processing_type.lower() and mech_second_pass) else 1
    if not mech_second_pass and "mechanical" in processing_type.lower():
        logger.info("MECH_SECOND_PASS=false → forcing single attempt for mechanical drawing")
    attempt = 0
    ai_error = None
    ai_error_message = "AI processing failed"

    while attempt < max_attempts and state["parsed_json_data"] is None:
        attempt += 1
        logger.info(
            f"Attempt {attempt}/{max_attempts} for AI processing of {file_name} (pipeline_id={pipeline_id})..."
        )
        
        try:
            # Process with AI
            structured_json_str = await process_drawing(
                raw_content=raw_content,
                drawing_type=processing_type,
                client=services["client"],
                pdf_path=pdf_path,
                titleblock_text=extraction_result.titleblock_text,
            )
            state["raw_ai_response_str"] = structured_json_str
            
            if not structured_json_str:
                logger.warning(f"AI service returned empty response on attempt {attempt}")
                ai_error_message = "AI returned empty response"
                break
            
            # Parse JSON response
            logger.info(f"Attempting to parse JSON response (length: {len(structured_json_str)} chars)...")
            
            # Determine if this drawing type needs JSON repair
            needs_repair = (
                "panel" in (state.get("subtype") or "").lower() or
                "mechanical" in processing_type.lower()
            )

            # Check for dedicated JSON repair toggle first
            json_repair_env = os.getenv("ENABLE_JSON_REPAIR")
            if json_repair_env is not None:
                # Explicit JSON repair setting takes precedence
                json_repair_enabled = json_repair_env.lower() == "true"
                if needs_repair and not json_repair_enabled:
                    logger.debug("JSON repair disabled by ENABLE_JSON_REPAIR=false")
            else:
                # Fallback to metadata repair setting for backward compatibility
                json_repair_enabled = get_enable_metadata_repair()
                if needs_repair and not json_repair_enabled:
                    logger.debug("JSON repair disabled by ENABLE_METADATA_REPAIR=false")

            # Parse with optional repair
            parsed_json = parse_json_safely(
                structured_json_str, 
                repair=(needs_repair and json_repair_enabled)
            )
            
            if parsed_json:
                state["parsed_json_data"] = parsed_json
                logger.info(f"Successfully parsed JSON response on attempt {attempt}")
                return state, True
            else:
                logger.warning(f"Failed to parse JSON response on attempt {attempt}")
                ai_error_message = "Failed to parse JSON response"
                
        except Exception as e:
            logger.error(f"Error processing with AI on attempt {attempt}: {str(e)}")
            ai_error = str(e)
            ai_error_message = f"AI processing error: {str(e)}"
            
        # If we get here, processing failed
        if attempt < max_attempts:
            logger.info(f"Retrying AI processing for {file_name}...")
            await asyncio.sleep(1)  # Brief delay before retry
    
    # If we get here, all attempts failed
    logger.error(f"All AI processing attempts failed for {file_name}")
    state["final_status_dict"] = {
        "success": False,
        "status": ProcessingStatus.AI_PROCESSING_FAILED,
        "error": ai_error_message,
        "file": pdf_path,
        "output_file": error_output_path,
        "message": None,
        "source_document": state.get("source_document_info"),
    }
    return state, False


async def step_validate_drawing_metadata(
    state: ProcessingState,
    services: PipelineServices,
    pdf_path: str,
) -> ProcessingState:
    """
    Validate drawing metadata with flexible schema.
    
    Note: Mutates state in place (though this step doesn't modify state).
    
    Args:
        state: Processing state
        services: Pipeline services bundle
        pdf_path: Path to the PDF file
        
    Returns:
        Updated state
    """
    logger = services["logger"]
    
    parsed_json = state["parsed_json_data"]
    if not parsed_json or "DRAWING_METADATA" not in parsed_json:
        return state
        
    try:
        # Import flexible schema
        from schemas.metadata import FlexibleDrawingMetadata
        
        # Use flexible validator
        metadata = parsed_json["DRAWING_METADATA"]
        validated_meta = FlexibleDrawingMetadata(**metadata)
        
        # Log at info level only if we have key fields
        if validated_meta.drawing_number or validated_meta.title:
            logger.info(
                "Drawing metadata validated",
                extra={
                    "file": pdf_path,
                    "drawing_number": validated_meta.drawing_number,
                    "revision": validated_meta.revision,
                },
            )
    except Exception as e:
        # Not critical - log at debug level
        logger.debug(
            f"Metadata validation note: {str(e)}",
            extra={"file": pdf_path}
        )
    
    return state

