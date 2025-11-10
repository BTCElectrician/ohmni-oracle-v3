"""
Extraction step for the processing pipeline.

Handles PDF content extraction and OCR augmentation.
"""
import math
import time
from typing import Tuple

from services.extraction_service import create_extractor
from config.settings import OCR_ENABLED, OCR_THRESHOLD, OCR_MAX_PAGES, FORCE_PANEL_OCR
from processing.pipeline.types import ProcessingState, ProcessingStatus
from processing.pipeline.services import PipelineServices
from processing.pipeline.constants import AVERAGE_CHARS_PER_TOKEN, OCR_TOKEN_THRESHOLD
from processing.pipeline.status import save_status_file


async def step_extract_content(
    state: ProcessingState,
    services: PipelineServices,
    file_name: str,
    error_output_path: str,
    structured_output_path: str,
) -> Tuple[ProcessingState, bool]:
    """
    Extract content from the PDF file.
    
    This step:
    1. Creates an appropriate extractor based on drawing type
    2. Extracts text and tables from the PDF
    3. Validates that the PDF contains useful content
    4. Handles OCR augmentation when needed
    
    Note: Mutates state in place.
    
    Args:
        state: Processing state (mutated in place)
        services: Pipeline services bundle
        file_name: Name of the PDF file being processed
        error_output_path: Path for error status files
        structured_output_path: Path for structured output files
        
    Returns:
        Tuple of (state, success) where success indicates extraction succeeded and content was found
    """
    logger = services["logger"]
    pdf_path = state["pdf_path"]
    
    extractor = create_extractor(state["original_drawing_type"], logger)
    extraction_result = await extractor.extract(pdf_path)
    state["extraction_result"] = extraction_result

    # Enhanced OCR validation metrics
    current_chars = len(extraction_result.raw_text.strip())
    
    # Expected character ranges by drawing type (for logging context only)
    processing_drawing_type = state["processing_type_for_ai"] or "General"
    drawing_type = processing_drawing_type.lower()
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
            with fitz.open(pdf_path) as doc:
                page_count = len(doc)
                chars_per_page = current_chars / page_count if page_count > 0 else current_chars
        except Exception as e:
            page_count = 1
            chars_per_page = current_chars
            logger.warning(f"Could not read PDF for page count: {e}")
    
    # Get intelligent OCR decision
    from services.ocr_service import should_perform_ocr
    should_ocr, decision_reason = should_perform_ocr(
        extracted_text=extraction_result.raw_text,
        pdf_path=pdf_path,
        page_count=page_count,
        ocr_enabled=OCR_ENABLED,
        ocr_threshold=OCR_THRESHOLD
    )

    is_panel_schedule_doc = (
        "panel" in file_name.lower()
        or "panel" in drawing_type
        or "panel" in (state.get("subtype") or "").lower()
    )
    if FORCE_PANEL_OCR and OCR_ENABLED and is_panel_schedule_doc:
        if not should_ocr:
            logger.info(
                "FORCE_PANEL_OCR enabled – overriding OCR decision for panel schedule document"
            )
        should_ocr = True
        decision_reason = "FORCE_PANEL_OCR override for panel schedule"
    
    # Create enhanced OCR decision metrics
    estimated_tokens = math.ceil(current_chars / AVERAGE_CHARS_PER_TOKEN) if current_chars > 0 else 0

    ocr_decision_metrics = {
        "performed": False,
        "reason": decision_reason,
        "chars_extracted": current_chars,
        "char_count_total": current_chars,
        "chars_per_page": round(chars_per_page, 1),
        "page_count": page_count,
        "threshold_per_page": OCR_THRESHOLD,
        "char_count_threshold": OCR_THRESHOLD,
        "drawing_type": processing_drawing_type,
        "expected_chars_per_page": expected_chars_per_page,
        "ocr_enabled": OCR_ENABLED,
        "should_ocr": should_ocr,
        "force_panel_ocr": FORCE_PANEL_OCR and is_panel_schedule_doc,
        "estimated_tokens": estimated_tokens,
        "token_threshold": OCR_TOKEN_THRESHOLD,
        "tiles_processed": 0,
    }
    
    logger.info(f"🔍 OCR Analysis: {current_chars} chars total ({chars_per_page:.0f}/page), threshold={OCR_THRESHOLD}/page, decision='{decision_reason}'")

    if OCR_ENABLED:
        try:
            from services.ocr_service import run_ocr_if_needed, OCRRunResult
            
            # Time the OCR operation for metrics
            ocr_start_time = time.time()
            
            ocr_payload = await run_ocr_if_needed(
                client=services["client"],
                pdf_path=pdf_path,
                current_text=extraction_result.raw_text,
                threshold=OCR_THRESHOLD,
                max_pages=OCR_MAX_PAGES,
                page_count=page_count,
                assume_ocr_needed=should_ocr,
                drawing_type=processing_drawing_type,
            )
            if isinstance(ocr_payload, OCRRunResult):
                ocr_text = ocr_payload.text
                ocr_decision_metrics["tiles_processed"] = ocr_payload.tiles_processed
            else:
                ocr_text = ocr_payload or ""
            
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
                    "ocr_processing", file_name, 
                    state["processing_type_for_ai"], ocr_duration
                )
                
                extraction_result.raw_text += ocr_text
                extraction_result.has_content = True
                logger.info(f"✅ OCR SUCCESS: Added {len(ocr_text)} characters in {ocr_duration:.2f}s")
            else:
                # OCR service already logged why it was skipped
                ocr_decision_metrics["ocr_duration_seconds"] = round(ocr_duration, 2)
                
            # Save OCR decision metrics to performance tracker as context
            try:
                from utils.performance_utils import get_tracker
                tracker = get_tracker()
                tracker.add_metric_with_context(
                    category="ocr_decision",
                    duration=ocr_duration,
                    file_path=pdf_path,
                    drawing_type=processing_drawing_type,
                    **ocr_decision_metrics,
                )
            except:
                pass
                
        except Exception as e:
            ocr_duration = time.time() - ocr_start_time if 'ocr_start_time' in locals() else 0
            
            # Update metrics for failed OCR
            ocr_decision_metrics["performed"] = False
            ocr_decision_metrics["reason"] = f"OCR failed: {str(e)}"
            ocr_decision_metrics["ocr_duration_seconds"] = round(ocr_duration, 2)
            
            logger.warning(f"❌ OCR FAILED after {ocr_duration:.2f}s: {e}")
            
            # Track failed OCR attempts
            try:
                from utils.performance_utils import get_tracker
                tracker = get_tracker()
                tracker.add_metric(
                    "ocr_processing", file_name + "_FAILED", 
                    state["processing_type_for_ai"], ocr_duration
                )
                tracker.add_metric_with_context(
                    category="ocr_decision",
                    duration=ocr_duration,
                    file_path=pdf_path,
                    drawing_type=processing_drawing_type,
                    **ocr_decision_metrics,
                )
            except:
                pass
    else:
        # OCR is disabled - still track the decision
        try:
            from utils.performance_utils import get_tracker
            tracker = get_tracker()
            tracker.add_metric_with_context(
                category="ocr_decision",
                duration=0,
                file_path=pdf_path,
                drawing_type=processing_drawing_type,
                **ocr_decision_metrics,
            )
        except:
            pass

    if not extraction_result.success:
        from processing.pipeline.persist import save_pipeline_status
        await save_pipeline_status(
            state, services, ProcessingStatus.EXTRACTION_FAILED,
            f"Extraction failed: {extraction_result.error}",
            error_output_path, True
        )
        return state, False
    
    if not extraction_result.has_content:
        from processing.pipeline.persist import save_pipeline_status
        await save_pipeline_status(
            state, services, ProcessingStatus.SKIPPED_UNREADABLE,
            "Skipped: No significant machine-readable content found.",
            structured_output_path, False
        )
        return state, False  

    # Optionally validate extraction metadata
    try:
        from schemas.metadata import ExtractionResultMetadata
        extraction_meta = ExtractionResultMetadata(**extraction_result.metadata)
        logger.info(
            "Extraction metadata validated",
            extra={"file": pdf_path, "page_count": extraction_meta.page_count},
        )
    except Exception as e:
        logger.warning(
            "Metadata validation setup failed",
            extra={"file": pdf_path, "error": str(e)},
        )
        # Continue processing despite validation failure

    return state, True

