"""
Normalization step for the processing pipeline.

Normalizes parsed data based on drawing type and subtype.
"""
from services.normalizers import normalize_panel_fields, normalize_mechanical_schedule, normalize_plumbing_schedule
from utils.performance_utils import time_operation_context
from processing.pipeline.types import ProcessingState
from processing.pipeline.services import PipelineServices
from tools.schedule_postpass.panel_text_postpass import (
    fill_panels_from_sheet_text,
    is_panel_schedule_sheet,
)


async def step_normalize_data(
    state: ProcessingState,
    services: PipelineServices,
    pdf_path: str,
    file_name: str,
) -> ProcessingState:
    """
    Normalize parsed data based on drawing type and subtype.
    
    This step:
    1. Determines if normalization is needed based on drawing type/subtype
    2. Applies appropriate normalization function
    3. Updates the processing state with normalized data
    
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
    
    parsed_json = state["parsed_json_data"]
    if not parsed_json:
        return state
        
    subtype = state.get("subtype")
    processing_type = state["processing_type_for_ai"]
    
    # Determine which normalization to apply
    is_panel_schedule = "panel" in (subtype or "").lower()
    is_mechanical_schedule = (
        "mechanical" in processing_type.lower() and 
        ("schedule" in (subtype or "").lower() or "schedule" in file_name.lower())
    )
    is_plumbing_schedule = (
        "plumbing" in processing_type.lower() and 
        "schedule" in (subtype or "").lower()
    )
    
    # Apply panel post-pass before normalization if applicable
    if is_panel_schedule:
        extraction_result = state.get("extraction_result")
        if extraction_result and extraction_result.raw_text:
            sheet_text = extraction_result.raw_text
            if is_panel_schedule_sheet(parsed_json):
                try:
                    logger.info(f"Running panel text post-pass for {file_name}")
                    client = services["client"]
                    parsed_json = await fill_panels_from_sheet_text(
                        sheet_json=parsed_json,
                        sheet_text=sheet_text,
                        client=client,
                    )
                    state["parsed_json_data"] = parsed_json
                except Exception as e:
                    logger.warning(
                        f"Panel post-pass failed for {file_name}: {e}, continuing with original data",
                        exc_info=True
                    )
    
    # Apply appropriate normalization
    with time_operation_context(
        "normalization",
        file_path=pdf_path,
        drawing_type=state["processing_type_for_ai"]
    ):
        if is_panel_schedule:
            logger.info(f"Normalizing panel fields for {file_name}")
            normalized_json = normalize_panel_fields(parsed_json)
            state["parsed_json_data"] = normalized_json
            
        elif is_mechanical_schedule:
            logger.info(f"Normalizing mechanical schedule for {file_name}")
            normalized_json = normalize_mechanical_schedule(parsed_json)
            state["parsed_json_data"] = normalized_json
            
        elif is_plumbing_schedule:
            logger.info(f"Normalizing plumbing schedule for {file_name}")
            normalized_json = normalize_plumbing_schedule(parsed_json)
            state["parsed_json_data"] = normalized_json
    
    return state

