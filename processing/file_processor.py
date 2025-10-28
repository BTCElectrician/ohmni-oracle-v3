# processing/file_processor.py
import os
import logging
import asyncio
import json
import uuid
import time
from enum import Enum, auto
from typing import Dict, Any, Optional, List, TypedDict, Literal, cast
from tqdm.asyncio import tqdm

from openai import AsyncOpenAI
from pydantic import validate_call

from services.extraction_service import create_extractor, ExtractionResult
from services.ai_service import process_drawing
from services.storage_service import FileSystemStorage
from services.normalizers import normalize_panel_fields, normalize_mechanical_schedule, normalize_plumbing_schedule
from utils.performance_utils import time_operation, time_operation_context
from utils.drawing_utils import detect_drawing_info
from utils.json_utils import parse_json_safely
from schemas.metadata import DrawingMetadata
from utils.exceptions import FileSystemError
from config.settings import get_enable_metadata_repair


# Constants for status messages
class ProcessingStatus(str, Enum):
    """Enum for standard processing status values."""
    EXTRACTION_FAILED = "extraction_failed"
    SKIPPED_UNREADABLE = "skipped_unreadable"
    AI_PROCESSING_FAILED = "ai_processing_failed"
    JSON_SAVE_FAILED = "json_save_failed"
    PROCESSED = "processed"
    UNEXPECTED_ERROR = "unexpected_error"


# TypedDict for processing state
class ProcessingState(TypedDict):
    """Typed dictionary for tracking the pipeline processing state."""
    pdf_path: str
    original_drawing_type: str
    templates_created: Dict[str, bool]
    extraction_result: Optional[ExtractionResult]
    processing_type_for_ai: str
    subtype: Optional[str]
    raw_ai_response_str: Optional[str]
    parsed_json_data: Optional[Dict[str, Any]]
    final_status_dict: Optional[Dict[str, Any]]


# TypedDict for result dictionary
class ProcessingResult(TypedDict):
    """Typed dictionary for the processing result returned to callers."""
    success: bool
    status: str
    file: str
    output_file: str
    error: Optional[str]
    message: Optional[str]


# Helper function moved outside of class for reuse
async def _save_status_file(
    storage: FileSystemStorage,
    file_path: str,
    status: str,
    message: str,
    original_pdf_path: str,
) -> None:
    """
    Saves a JSON file indicating the processing status or error.
    
    Args:
        storage: Storage service to use for saving
        file_path: Path where the status file should be saved
        status: Status identifier
        message: Detailed status message
        original_pdf_path: Path to the original PDF file
        
    Raises:
        FileSystemError: If the status file cannot be saved
    """
    status_data = {
        "original_file": original_pdf_path,
        "status": status,
        "message": message,
        "timestamp": time.time(),
    }
    try:
        await storage.save_json(status_data, file_path)
        logging.getLogger(__name__).info(f"Saved status file ({status}) to: {file_path}")
    except Exception as e:
        logging.getLogger(__name__).error(
            "Failed to save status file",
            extra={"file_path": file_path, "status": status, "error": str(e)},
        )
        raise FileSystemError(f"Failed to save status file {file_path}: {e}")


class FileProcessingPipeline:
    """
    Processes a PDF file through a series of extraction, AI processing, 
    and normalization steps to produce structured data.
    
    This class implements a step-by-step pipeline that:
    1. Extracts content from a PDF
    2. Determines the appropriate drawing type for AI processing
    3. Sends content to AI for structured analysis
    4. Parses and validates the returned JSON
    5. Normalizes the data based on drawing type
    6. Saves the results to storage
    7. Optionally generates additional templates
    
    Each step is implemented as a separate method for clarity and maintainability.
    """

    def __init__(
        self, 
        pdf_path: str, 
        client: AsyncOpenAI, 
        output_folder: str, 
        drawing_type: str, 
        templates_created: Dict[str, bool], 
        storage: FileSystemStorage, 
        logger: logging.Logger
    ):
        """
        Initialize the processing pipeline.
        
        Args:
            pdf_path: Path to the PDF file to process
            client: OpenAI client for AI processing
            output_folder: Base folder for output files
            drawing_type: Type of drawing (e.g., "Architectural", "Electrical")
            templates_created: Dictionary tracking what templates have been created
            storage: FileSystemStorage instance for saving results
            logger: Logger instance for recording progress and errors
        """
        if not os.path.exists(pdf_path):
            raise ValueError(f"PDF file does not exist: {pdf_path}")
            
        self.pdf_path: str = pdf_path
        self.client: AsyncOpenAI = client
        self.templates_created: Dict[str, bool] = templates_created
        self.storage: FileSystemStorage = storage
        self.logger: logging.Logger = logger
        self.file_name: str = os.path.basename(pdf_path)
        self.pipeline_id: str = str(uuid.uuid4())
        
        # Set up output paths
        self.output_drawing_type_folder: str = drawing_type if drawing_type else "General"
        self.type_folder: str = os.path.join(output_folder, self.output_drawing_type_folder)
        os.makedirs(self.type_folder, exist_ok=True)
        
        output_filename_base: str = os.path.splitext(self.file_name)[0]
        self.structured_output_path: str = os.path.join(
            self.type_folder, f"{output_filename_base}_structured.json"
        )
        self.error_output_path: str = os.path.join(
            self.type_folder, f"{output_filename_base}_error.json"
        )
        self.raw_error_output_path: str = os.path.join(
            self.type_folder, f"{output_filename_base}_raw_response_error.txt"
        )

        # Initialize processing state
        self.processing_state: ProcessingState = {
            "pdf_path": pdf_path,
            "original_drawing_type": drawing_type,
            "templates_created": templates_created,
            "extraction_result": None,
            "processing_type_for_ai": drawing_type,  # initial value
            "subtype": None,
            "raw_ai_response_str": None,
            "parsed_json_data": None,
            "final_status_dict": None,
        }

    async def _save_pipeline_status(
        self, status: str, message: str, is_error: bool = True
    ) -> ProcessingResult:
        """
        Create and save pipeline status information, updating the processing state.
        
        Args:
            status: Status identifier
            message: Detailed status message
            is_error: Whether this status represents an error (default: True)
            
        Returns:
            Dictionary with status information to return to the caller
        """
        output_path: str = self.error_output_path if is_error else self.structured_output_path
        status_key: Literal["error", "message"] = "error" if is_error else "message"
        
        result_dict: ProcessingResult = {
            "success": not is_error,
            "status": status,
            "file": self.pdf_path,
            "output_file": output_path,
            "error": message if is_error else None,
            "message": message if not is_error else None,
        }
        
        await _save_status_file(
            self.storage,
            output_path,
            status,
            message,
            self.pdf_path,
        )
        self.processing_state["final_status_dict"] = result_dict
        return result_dict

    async def _step_extract_content(self) -> bool:
        """
        Extract content from the PDF file.
        
        This step:
        1. Creates an appropriate extractor based on drawing type
        2. Extracts text and tables from the PDF
        3. Validates that the PDF contains useful content
        4. Validates extraction metadata if possible
        
        Returns:
            True if extraction succeeded and content was found, False otherwise
        """
        extractor = create_extractor(self.processing_state["original_drawing_type"], self.logger)
        extraction_result = await extractor.extract(self.pdf_path)
        self.processing_state["extraction_result"] = extraction_result

        # OCR augmentation when needed
        from config.settings import OCR_ENABLED, OCR_THRESHOLD, OCR_MAX_PAGES
        
        # Enhanced OCR validation metrics
        current_chars = len(extraction_result.raw_text.strip())
        
        # Expected character ranges by drawing type (for logging context only)
        drawing_type = self.processing_state["processing_type_for_ai"].lower()
        expected_per_page_ranges = {
            "mechanical": "2000-3000 per page for schedules, 800-1500 for details",
            "electrical": "1500-2500 per page for panel schedules, 500-1000 for details", 
            "plumbing": "1200-2000 per page for schedules, 400-800 for details",
            "architectural": "1000-2000 per page for floor plans, 600-1200 for details",
            "general": "varies by drawing content and complexity"
        }
        expected_chars_per_page = expected_per_page_ranges.get(drawing_type.split('_')[0], "varies by drawing type")
        
        # Calculate pages for per-page analysis
        extraction_meta = extraction_result.metadata or {}
        meta_page_count = extraction_meta.get("page_count")
        
        if isinstance(meta_page_count, int) and meta_page_count > 0:
            # Use page count from extraction metadata (no need to reopen PDF)
            page_count = meta_page_count
            chars_per_page = current_chars / page_count if page_count > 0 else current_chars
        else:
            # Fallback: only open PDF if metadata is missing
            try:
                import pymupdf as fitz
                with fitz.open(self.pdf_path) as doc:
                    page_count = len(doc)
                    chars_per_page = current_chars / page_count if page_count > 0 else current_chars
            except Exception as e:
                page_count = 1
                chars_per_page = current_chars
                self.logger.warning(f"Could not read PDF for page count: {e}")
        
        # Get intelligent OCR decision
        from services.ocr_service import should_perform_ocr
        should_ocr, decision_reason = should_perform_ocr(
            extracted_text=extraction_result.raw_text,
            pdf_path=self.pdf_path,
            page_count=page_count,
            ocr_enabled=OCR_ENABLED,
            ocr_threshold=OCR_THRESHOLD
        )
        
        # Create enhanced OCR decision metrics
        ocr_decision_metrics = {
            "performed": False,
            "reason": decision_reason,
            "chars_extracted": current_chars,
            "chars_per_page": round(chars_per_page, 1),
            "page_count": page_count,
            "threshold_per_page": OCR_THRESHOLD,  # Now correctly documented as per-page
            "drawing_type": drawing_type,
            "expected_chars_per_page": expected_chars_per_page,
            "ocr_enabled": OCR_ENABLED,
            "should_ocr": should_ocr
        }
        
        self.logger.info(f"🔍 OCR Analysis: {current_chars} chars total ({chars_per_page:.0f}/page), threshold={OCR_THRESHOLD}/page, decision='{decision_reason}'")

        if OCR_ENABLED:
            try:
                from services.ocr_service import run_ocr_if_needed
                
                # Time the OCR operation for metrics
                ocr_start_time = time.time()
                
                ocr_text = await run_ocr_if_needed(
                    client=self.client,
                    pdf_path=self.pdf_path,
                    current_text=extraction_result.raw_text,
                    threshold=OCR_THRESHOLD,
                    max_pages=OCR_MAX_PAGES,
                    page_count=page_count,
                    assume_ocr_needed=should_ocr
                )
                
                ocr_duration = time.time() - ocr_start_time
                
                # Update OCR decision metrics with results
                if ocr_text:
                    ocr_decision_metrics["performed"] = True
                    ocr_decision_metrics["ocr_chars_added"] = len(ocr_text)
                    ocr_decision_metrics["total_chars_after_ocr"] = current_chars + len(ocr_text)
                    ocr_decision_metrics["ocr_duration_seconds"] = round(ocr_duration, 2)
                    
                    # Track OCR metrics in performance system
                    from utils.performance_utils import get_tracker
                    tracker = get_tracker()
                    tracker.add_metric(
                        "ocr_processing", self.file_name, 
                        self.processing_state["processing_type_for_ai"], ocr_duration
                    )
                    
                    extraction_result.raw_text += ocr_text
                    extraction_result.has_content = True
                    self.logger.info(f"✅ OCR SUCCESS: Added {len(ocr_text)} characters in {ocr_duration:.2f}s")
                else:
                    # OCR service already logged why it was skipped
                    ocr_decision_metrics["ocr_duration_seconds"] = round(ocr_duration, 2)
                    
                # Save OCR decision metrics to performance tracker as context
                try:
                    from utils.performance_utils import get_tracker
                    tracker = get_tracker()
                    tracker.add_metric_with_context(
                        "ocr_decision", self.file_name,
                        self.processing_state["processing_type_for_ai"], 
                        ocr_duration, ocr_decision_metrics
                    )
                except:
                    pass
                    
            except Exception as e:
                ocr_duration = time.time() - ocr_start_time if 'ocr_start_time' in locals() else 0
                
                # Update metrics for failed OCR
                ocr_decision_metrics["performed"] = False
                ocr_decision_metrics["reason"] = f"OCR failed: {str(e)}"
                ocr_decision_metrics["ocr_duration_seconds"] = round(ocr_duration, 2)
                
                self.logger.warning(f"❌ OCR FAILED after {ocr_duration:.2f}s: {e}")
                
                # Track failed OCR attempts
                try:
                    from utils.performance_utils import get_tracker
                    tracker = get_tracker()
                    tracker.add_metric(
                        "ocr_processing", self.file_name + "_FAILED", 
                        self.processing_state["processing_type_for_ai"], ocr_duration
                    )
                    tracker.add_metric_with_context(
                        "ocr_decision", self.file_name + "_FAILED",
                        self.processing_state["processing_type_for_ai"], 
                        ocr_duration, ocr_decision_metrics
                    )
                except:
                    pass
        else:
            # OCR is disabled - still track the decision
            try:
                from utils.performance_utils import get_tracker
                tracker = get_tracker()
                tracker.add_metric_with_context(
                    "ocr_decision", self.file_name,
                    self.processing_state["processing_type_for_ai"], 
                    0, ocr_decision_metrics
                )
            except:
                pass

        if not extraction_result.success:
            await self._save_pipeline_status(
                ProcessingStatus.EXTRACTION_FAILED, 
                f"Extraction failed: {extraction_result.error}"
            )
            return False
        
        if not extraction_result.has_content:
            await self._save_pipeline_status(
                ProcessingStatus.SKIPPED_UNREADABLE, 
                "Skipped: No significant machine-readable content found.", 
                is_error=False
            )
            return False  

        # Optionally validate extraction metadata
        try:
            from schemas.metadata import ExtractionResultMetadata
            extraction_meta = ExtractionResultMetadata(**extraction_result.metadata)
            self.logger.info(
                "Extraction metadata validated",
                extra={"file": self.pdf_path, "page_count": extraction_meta.page_count},
            )
        except Exception as e:
            self.logger.warning(
                "Metadata validation setup failed",
                extra={"file": self.pdf_path, "error": str(e)},
            )
            # Continue processing despite validation failure

        return True

    async def _step_determine_ai_processing_type(self) -> None:
        """
        Determine the appropriate drawing type for AI processing.
        
        This step:
        1. Detects drawing info from filename
        2. Uses original drawing type or detected type
        3. Handles special cases like specification documents
        4. Updates the processing state with the determined type
        """
        main_type, subtype = detect_drawing_info(self.file_name)
        processing_type = self.processing_state["original_drawing_type"]
        
        if not processing_type or processing_type == "General":
            processing_type = main_type
            self.logger.info(f"Using detected drawing type for AI processing: {processing_type}")
        
        # Special handling for specification documents
        if "spec" in self.pdf_path.lower() or "specification" in self.pdf_path.lower():
            discipline_code = os.path.basename(self.pdf_path)[0].upper()
            prompt_map = {
                "E": "ELECTRICAL_SPEC", 
                "M": "MECHANICAL_SPEC",
                "P": "PLUMBING_SPEC", 
                "A": "ARCHITECTURAL_SPEC",
            }
            processing_type = prompt_map.get(discipline_code, "GENERAL_SPEC")
            self.logger.info(f"Detected specification document, using prompt: {processing_type}")
        
        self.logger.info(f"Processing content for PDF {self.file_name} as {processing_type} (subtype: {subtype})")
        self.processing_state["processing_type_for_ai"] = processing_type
        self.processing_state["subtype"] = subtype

    async def _step_ai_processing_and_parsing(self) -> bool:
        """
        Process extracted content with AI and parse the response.
        
        This step:
        1. Gets raw content from extraction result
        2. Processes with AI using appropriate drawing type
        3. Parses and validates the JSON response
        4. Updates the processing state with results
        
        Returns:
            True if processing succeeded, False otherwise
        """
        extraction_result = self.processing_state["extraction_result"]
        if not extraction_result or not extraction_result.success:
            self.logger.error(f"Extraction failed for {self.file_name}")
            return False

        raw_content = extraction_result.raw_text
        processing_type = self.processing_state["processing_type_for_ai"]

        # Add tables to raw content
        for table in extraction_result.tables:
            raw_content += f"\nTABLE:\n{table['content']}\n"

        # Process with AI
        mech_second_pass = os.getenv("MECH_SECOND_PASS", "true").lower() == "true"
        max_attempts = 2 if ("mechanical" in processing_type.lower() and mech_second_pass) else 1
        if not mech_second_pass and "mechanical" in processing_type.lower():
            self.logger.info("MECH_SECOND_PASS=false → forcing single attempt for mechanical drawing")
        attempt = 0
        ai_error = None

        while attempt < max_attempts and self.processing_state["parsed_json_data"] is None:
            attempt += 1
            self.logger.info(
                f"Attempt {attempt}/{max_attempts} for AI processing of {self.file_name} (pipeline_id={self.pipeline_id})..."
            )
            
            try:
                # Process with AI
                structured_json_str = await process_drawing(
                    raw_content=raw_content,
                    drawing_type=processing_type,
                    client=self.client,
                    pdf_path=self.pdf_path,
                    titleblock_text=extraction_result.titleblock_text,
                )
                self.processing_state["raw_ai_response_str"] = structured_json_str
                
                if not structured_json_str:
                    self.logger.warning(f"AI service returned empty response on attempt {attempt}")
                    ai_error_message = "AI returned empty response"
                    break
                
                # Parse JSON response
                self.logger.info(f"Attempting to parse JSON response (length: {len(structured_json_str)} chars)...")
                
                # Determine if this drawing type needs JSON repair
                needs_repair = (
                    "panel" in (self.processing_state.get("subtype") or "").lower() or
                    "mechanical" in processing_type.lower()
                )

                # Check for dedicated JSON repair toggle first
                json_repair_env = os.getenv("ENABLE_JSON_REPAIR")
                if json_repair_env is not None:
                    # Explicit JSON repair setting takes precedence
                    json_repair_enabled = json_repair_env.lower() == "true"
                    if needs_repair and not json_repair_enabled:
                        self.logger.debug("JSON repair disabled by ENABLE_JSON_REPAIR=false")
                else:
                    # Fallback to metadata repair setting for backward compatibility
                    json_repair_enabled = get_enable_metadata_repair()
                    if needs_repair and not json_repair_enabled:
                        self.logger.debug("JSON repair disabled by ENABLE_METADATA_REPAIR=false")

                # Parse with optional repair
                parsed_json = parse_json_safely(
                    structured_json_str, 
                    repair=(needs_repair and json_repair_enabled)
                )
                
                if parsed_json:
                    self.processing_state["parsed_json_data"] = parsed_json
                    self.logger.info(f"Successfully parsed JSON response on attempt {attempt}")
                    return True
                else:
                    self.logger.warning(f"Failed to parse JSON response on attempt {attempt}")
                    ai_error_message = "Failed to parse JSON response"
                    
            except Exception as e:
                self.logger.error(f"Error processing with AI on attempt {attempt}: {str(e)}")
                ai_error = str(e)
                ai_error_message = f"AI processing error: {str(e)}"
                
            # If we get here, processing failed
            if attempt < max_attempts:
                self.logger.info(f"Retrying AI processing for {self.file_name}...")
                await asyncio.sleep(1)  # Brief delay before retry
        
        # If we get here, all attempts failed
        self.logger.error(f"All AI processing attempts failed for {self.file_name}")
        self.processing_state["final_status_dict"] = {
            "success": False,
            "status": ProcessingStatus.AI_PROCESSING_FAILED,
            "error": ai_error_message,
            "file": self.pdf_path,
            "output_file": self.error_output_path,
            "message": None,
        }
        return False

    async def _step_validate_drawing_metadata(self) -> None:
        """
        Validate drawing metadata with flexible schema.
        """
        parsed_json = self.processing_state["parsed_json_data"]
        if not parsed_json or "DRAWING_METADATA" not in parsed_json:
            return
            
        try:
            # Import flexible schema
            from schemas.metadata import FlexibleDrawingMetadata
            
            # Use flexible validator
            metadata = parsed_json["DRAWING_METADATA"]
            validated_meta = FlexibleDrawingMetadata(**metadata)
            
            # Log at info level only if we have key fields
            if validated_meta.drawing_number or validated_meta.title:
                self.logger.info(
                    "Drawing metadata validated",
                    extra={
                        "file": self.pdf_path,
                        "drawing_number": validated_meta.drawing_number,
                        "revision": validated_meta.revision,
                    },
                )
        except Exception as e:
            # Not critical - log at debug level
            self.logger.debug(
                f"Metadata validation note: {str(e)}",
                extra={"file": self.pdf_path}
            )

    async def _step_normalize_data(self) -> None:
        """
        Normalize parsed data based on drawing type and subtype.
        
        This step:
        1. Determines if normalization is needed based on drawing type/subtype
        2. Applies appropriate normalization function
        3. Updates the processing state with normalized data
        """
        parsed_json = self.processing_state["parsed_json_data"]
        if not parsed_json:
            return
            
        subtype = self.processing_state.get("subtype")
        processing_type = self.processing_state["processing_type_for_ai"]
        
        # Determine which normalization to apply
        is_panel_schedule = "panel" in (subtype or "").lower()
        is_mechanical_schedule = (
            "mechanical" in processing_type.lower() and 
            ("schedule" in (subtype or "").lower() or "schedule" in self.file_name.lower())
        )
        is_plumbing_schedule = (
            "plumbing" in processing_type.lower() and 
            "schedule" in (subtype or "").lower()
        )
        
        # Apply appropriate normalization
        with time_operation_context(
            "normalization",
            file_path=self.pdf_path,
            drawing_type=self.processing_state["processing_type_for_ai"]
        ):
            if is_panel_schedule:
                self.logger.info(f"Normalizing panel fields for {self.file_name}")
                normalized_json = normalize_panel_fields(parsed_json)
                self.processing_state["parsed_json_data"] = normalized_json
                
            elif is_mechanical_schedule:
                self.logger.info(f"Normalizing mechanical schedule for {self.file_name}")
                normalized_json = normalize_mechanical_schedule(parsed_json)
                self.processing_state["parsed_json_data"] = normalized_json
                
            elif is_plumbing_schedule:
                self.logger.info(f"Normalizing plumbing schedule for {self.file_name}")
                normalized_json = normalize_plumbing_schedule(parsed_json)
                self.processing_state["parsed_json_data"] = normalized_json

    async def _step_save_output(self) -> bool:
        """
        Save the processed data to the output file.
        
        Returns:
            True if save was successful, False otherwise
        """
        try:
            await self.storage.save_json(
                self.processing_state["parsed_json_data"],
                self.structured_output_path
            )
            self.logger.info(f"✅ Completed {self.file_name}")
            
            # Set the success status
            self.processing_state["final_status_dict"] = {
                "success": True,
                "status": ProcessingStatus.PROCESSED,
                "file": self.pdf_path,
                "output_file": self.structured_output_path,
                "error": None,
                "message": "Processing completed successfully",
            }
            
            return True
        except Exception as e:
            self.logger.error(f"Error saving output file: {str(e)}")
            
            # Set the error status
            await self._save_pipeline_status(
                ProcessingStatus.JSON_SAVE_FAILED,
                f"Failed to save output: {str(e)}"
            )
            
            return False

    async def _step_generate_room_templates(self) -> None:
        """
        Generate room templates for architectural drawings.
        
        This step:
        1. Checks if the drawing is an architectural floor plan
        2. Generates room templates if applicable
        3. Updates templates_created tracking dictionary
        
        This is an optional post-processing step.
        """
        if self.processing_state["processing_type_for_ai"] == "Architectural" and "floor" in self.file_name.lower():
            try:
                from templates.room_templates import process_architectural_drawing
                
                result = process_architectural_drawing(
                    self.processing_state["parsed_json_data"], 
                    self.pdf_path, 
                    self.type_folder
                )
                
                self.processing_state["templates_created"]["floor_plan"] = True
                self.logger.info(f"Created room templates: {result}")
                
            except Exception as e:
                self.logger.error(f"Error creating room templates for {self.file_name}: {str(e)}")
                # Continue processing despite template generation failure

    @time_operation("total_processing")
    async def process(self) -> ProcessingResult:
        """
        Process the PDF file through the complete pipeline.
        
        Returns:
            Dictionary with processing results
        """
        self.logger.info(f"PIPELINE_START file={self.file_name} pipeline_id={self.pipeline_id}")
        self.logger.info(f"🔄 Processing {self.file_name}")
        try:
            with tqdm(total=100, desc=f"Processing {self.file_name}", leave=False) as pbar:
                # Step 1: Extract content
                if not await self._step_extract_content():
                    pbar.update(100)
                    self.logger.info(f"PIPELINE_END file={self.file_name} pipeline_id={self.pipeline_id}")
                    return cast(ProcessingResult, self.processing_state["final_status_dict"])
                pbar.update(20)

                # Step 2: Determine AI processing type
                await self._step_determine_ai_processing_type()
                pbar.update(10)

                # Step 3: AI processing and parsing
                if not await self._step_ai_processing_and_parsing():
                    pbar.update(70)  # remaining progress
                    self.logger.info(f"PIPELINE_END file={self.file_name} pipeline_id={self.pipeline_id}")
                    return cast(ProcessingResult, self.processing_state["final_status_dict"])
                pbar.update(40)  # AI + Parse

                # Step 4: Validate drawing metadata (optional)
                await self._step_validate_drawing_metadata()
                
                # Step 5: Normalize data
                await self._step_normalize_data()
                pbar.update(10)  # Normalization

                # Step 6: Save output
                if not await self._step_save_output():
                    pbar.update(20)  # remaining progress
                    self.logger.info(f"PIPELINE_END file={self.file_name} pipeline_id={self.pipeline_id}")
                    return cast(ProcessingResult, self.processing_state["final_status_dict"])
                pbar.update(10)  # Save

                # Step 7: Generate room templates (optional)
                await self._step_generate_room_templates()
                pbar.update(10)  # Room templates

                # Return final result
                self.logger.info(f"PIPELINE_END file={self.file_name} pipeline_id={self.pipeline_id}")
                return cast(ProcessingResult, self.processing_state["final_status_dict"])
        except Exception as e:
            self.logger.error(f"Unexpected error in processing pipeline: {str(e)}", exc_info=True)
            self.logger.info(f"PIPELINE_END file={self.file_name} pipeline_id={self.pipeline_id}")
            return await self._save_pipeline_status(
                ProcessingStatus.UNEXPECTED_ERROR, 
                f"Unexpected pipeline error: {str(e)}"
            )


@validate_call(config=dict(arbitrary_types_allowed=True))
async def process_pdf_async(
    pdf_path: str,
    client: AsyncOpenAI,
    output_folder: str,
    drawing_type: str,
    templates_created: Dict[str, bool],
) -> ProcessingResult:
    """
    Process a single PDF file through the extraction and AI processing pipeline.
    
    Args:
        pdf_path: Path to the PDF file to process
        client: OpenAI client for AI processing
        output_folder: Folder to store output files
        drawing_type: Type of drawing (e.g., "Architectural", "Electrical") 
        templates_created: Dictionary tracking what templates have been created
        
    Returns:
        Dictionary with processing result information
        
    This function is the main entry point for processing a PDF file and uses
    the FileProcessingPipeline class to manage the processing steps.
    """
    logger_instance = logging.getLogger(__name__)
    storage = FileSystemStorage(logger_instance)
    
    try:
        pipeline = FileProcessingPipeline(
            pdf_path, client, output_folder, drawing_type, 
            templates_created, storage, logger_instance
        )
        return await pipeline.process()
    except Exception as e:
        # Catch-all for unexpected errors
        logger_instance.error(f"Unexpected error processing {pdf_path}: {str(e)}", exc_info=True)
        
        # Create error output path
        filename_base = os.path.splitext(os.path.basename(pdf_path))[0]
        output_type_folder = drawing_type if drawing_type else "General"
        type_folder = os.path.join(output_folder, output_type_folder)
        os.makedirs(type_folder, exist_ok=True)
        error_output_path = os.path.join(type_folder, f"{filename_base}_error.json")
        
        # Save error status
        await _save_status_file(
            storage, error_output_path, 
            ProcessingStatus.UNEXPECTED_ERROR, str(e), pdf_path
        )
        
        # Return error result
        return {
            "success": False,
            "status": ProcessingStatus.UNEXPECTED_ERROR,
            "error": f"Unexpected error processing {pdf_path}: {str(e)}",
            "file": pdf_path,
            "output_file": error_output_path,
            "message": None,
        }
