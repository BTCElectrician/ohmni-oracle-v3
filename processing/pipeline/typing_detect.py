"""
Type detection step for the processing pipeline.

Determines the appropriate drawing type for AI processing.
"""
import os

from utils.drawing_utils import detect_drawing_info
from processing.pipeline.types import ProcessingState
from processing.pipeline.services import PipelineServices


async def step_determine_ai_processing_type(
    state: ProcessingState,
    services: PipelineServices,
    pdf_path: str,
    file_name: str,
) -> ProcessingState:
    """
    Determine the appropriate drawing type for AI processing.
    
    This step:
    1. Detects drawing info from filename
    2. Uses original drawing type or detected type
    3. Handles special cases like specification documents
    4. Updates the processing state with the determined type
    
    Note: Mutates state in place.
    
    Args:
        state: Processing state (mutated in place)
        services: Pipeline services bundle
        pdf_path: Path to the PDF file
        file_name: Name of the PDF file
        
    Returns:
        Updated state
    """
    logger = services["logger"]
    
    main_type, subtype = detect_drawing_info(file_name)
    processing_type = state["original_drawing_type"]
    
    if not processing_type or processing_type == "General":
        processing_type = main_type
        logger.info(f"Using detected drawing type for AI processing: {processing_type}")
    
    # Special handling for specification documents
    if "spec" in pdf_path.lower() or "specification" in pdf_path.lower():
        discipline_code = os.path.basename(pdf_path)[0].upper()
        prompt_map = {
            "E": "ELECTRICAL_SPEC", 
            "M": "MECHANICAL_SPEC",
            "P": "PLUMBING_SPEC", 
            "A": "ARCHITECTURAL_SPEC",
        }
        processing_type = prompt_map.get(discipline_code, "GENERAL_SPEC")
        logger.info(f"Detected specification document, using prompt: {processing_type}")
    
    logger.info(f"Processing content for PDF {file_name} as {processing_type} (subtype: {subtype})")
    state["processing_type_for_ai"] = processing_type
    state["subtype"] = subtype
    
    return state

