"""
Type definitions for the processing pipeline.

Contains enums and TypedDicts used throughout the pipeline.
"""
from enum import Enum
from typing import Dict, Any, Optional, TypedDict

from services.extraction_service import ExtractionResult
from services.storage_service import StoredFileInfo


class ProcessingStatus(str, Enum):
    """Enum for standard processing status values."""
    EXTRACTION_FAILED = "extraction_failed"
    SKIPPED_UNREADABLE = "skipped_unreadable"
    AI_PROCESSING_FAILED = "ai_processing_failed"
    JSON_SAVE_FAILED = "json_save_failed"
    SOURCE_ARCHIVE_FAILED = "source_archive_failed"
    PROCESSED = "processed"
    UNEXPECTED_ERROR = "unexpected_error"


class ProcessingState(TypedDict):
    """Typed dictionary for tracking the pipeline processing state.
    
    Note: This dictionary is mutated in place by pipeline steps.
    No defensive copies are made - steps directly modify the state.
    """
    pdf_path: str
    original_drawing_type: str
    templates_created: Dict[str, bool]
    extraction_result: Optional[ExtractionResult]
    processing_type_for_ai: str
    subtype: Optional[str]
    raw_ai_response_str: Optional[str]
    parsed_json_data: Optional[Dict[str, Any]]
    final_status_dict: Optional[Dict[str, Any]]
    source_document_info: Optional[StoredFileInfo]
    structured_document_info: Optional[StoredFileInfo]
    template_files: list


class ProcessingResult(TypedDict):
    """Typed dictionary for the processing result returned to callers."""
    success: bool
    status: str
    file: str
    output_file: str
    error: Optional[str]
    message: Optional[str]
    source_document: Optional[Dict[str, Any]]
    structured_document: Optional[Dict[str, Any]]

