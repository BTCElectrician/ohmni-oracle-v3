"""
Persistence operations for the processing pipeline.

Handles saving output files and metadata manifests.
"""
import os
from typing import Tuple, Any, Dict

from utils.exceptions import FileSystemError
from processing.pipeline.types import ProcessingState, ProcessingStatus, ProcessingResult
from processing.pipeline.services import PipelineServices
from processing.pipeline.status import save_status_file
from processing.pipeline.archive import (
    archive_original_document,
    archive_structured_output,
    attach_source_reference,
)


async def save_pipeline_status(
    state: ProcessingState,
    services: PipelineServices,
    status: str,
    message: str,
    output_path: str,
    is_error: bool = True,
) -> ProcessingResult:
    """
    Create and save pipeline status information, updating the processing state.
    
    Note: Mutates state in place.
    
    Args:
        state: Processing state (mutated in place)
        services: Pipeline services bundle
        status: Status identifier
        message: Detailed status message
        output_path: Path where status file should be saved
        is_error: Whether this status represents an error (default: True)
        
    Returns:
        Dictionary with status information to return to the caller
    """
    result_dict: ProcessingResult = {
        "success": not is_error,
        "status": status,
        "file": state["pdf_path"],
        "output_file": output_path,
        "error": message if is_error else None,
        "message": message if not is_error else None,
        "source_document": state.get("source_document_info"),
        "structured_document": state.get("structured_document_info"),
    }
    
    await save_status_file(
        services["storage"],
        output_path,
        status,
        message,
        state["pdf_path"],
    )
    state["final_status_dict"] = result_dict
    return result_dict


async def step_save_output(
    state: ProcessingState,
    services: PipelineServices,
    pdf_path: str,
    file_name: str,
    pipeline_id: str,
    structured_output_path: str,
    error_output_path: str,
    storage_discipline: str,
    drawing_slug: str,
    tenant_id: str,
) -> Tuple[ProcessingState, bool]:
    """
    Save the processed data to the output file.
    
    Note: Mutates state in place.
    
    Args:
        state: Processing state (mutated in place)
        services: Pipeline services bundle
        pdf_path: Path to the PDF file
        file_name: Name of the PDF file
        pipeline_id: Unique pipeline identifier
        structured_output_path: Path for structured output file
        error_output_path: Path for error status files
        storage_discipline: Storage discipline slug
        drawing_slug: Drawing slug identifier
        
    Returns:
        Tuple of (state, success) where success indicates save was successful
    """
    logger = services["logger"]
    
    archived_info = None
    try:
        archived_info = await archive_original_document(
            state, services, pdf_path, file_name, pipeline_id,
            storage_discipline, drawing_slug
        )
    except FileSystemError as exc:
        await save_pipeline_status(
            state, services, ProcessingStatus.SOURCE_ARCHIVE_FAILED,
            str(exc), error_output_path, True
        )
        if state["final_status_dict"]:
            state["final_status_dict"]["source_document"] = state.get("source_document_info")
            state["final_status_dict"]["structured_document"] = state.get("structured_document_info")
        return state, False

    if archived_info:
        attach_source_reference(state, archived_info, file_name)

    try:
        # Add tenant_id to parsed JSON before saving
        parsed_json = state["parsed_json_data"]
        if isinstance(parsed_json, dict):
            parsed_json["tenant_id"] = tenant_id
        
        saved = await services["storage"].save_json(
            parsed_json,
            structured_output_path,
        )
        if not saved:
            raise FileSystemError("Storage backend reported failure while saving structured JSON output")

        logger.info(f"✅ Completed {file_name}")
        structured_info = await archive_structured_output(
            state, services, structured_output_path, file_name, pipeline_id,
            storage_discipline, drawing_slug
        )

        state["final_status_dict"] = {
            "success": True,
            "status": ProcessingStatus.PROCESSED,
            "file": pdf_path,
            "output_file": structured_output_path,
            "error": None,
            "message": "Processing completed successfully",
            "source_document": archived_info or state.get("source_document_info"),
            "structured_document": structured_info or state.get("structured_document_info"),
        }

        return state, True
    except FileSystemError as exc:
        logger.error(f"File system error while saving output: {exc}")
        await save_pipeline_status(
            state, services, ProcessingStatus.JSON_SAVE_FAILED,
            f"Failed to save output: {exc}", error_output_path, True
        )
    except Exception as e:
        logger.error(f"Error saving output file: {str(e)}", exc_info=True)
        await save_pipeline_status(
            state, services, ProcessingStatus.JSON_SAVE_FAILED,
            f"Failed to save output: {str(e)}", error_output_path, True
        )

    if state["final_status_dict"]:
        state["final_status_dict"]["source_document"] = state.get("source_document_info")
        state["final_status_dict"]["structured_document"] = state.get("structured_document_info")
    return state, False


async def step_save_metadata(
    state: ProcessingState,
    services: PipelineServices,
    pdf_path: str,
    file_name: str,
    pipeline_id: str,
    structured_output_path: str,
    structured_folder: str,
    templates_folder: str,
    meta_file_path: str,
    drawing_slug: str,
    output_drawing_type_folder: str,
    version_folder: str,
    output_base_folder: str,
    tenant_id: str,
) -> ProcessingState:
    """Persist a lightweight metadata manifest for the processed drawing.
    
    Note: Mutates state in place (though this step doesn't modify state).
    
    Args:
        state: Processing state
        services: Pipeline services bundle
        pdf_path: Path to the PDF file
        file_name: Name of the PDF file
        pipeline_id: Unique pipeline identifier
        structured_output_path: Path to structured output file
        structured_folder: Path to structured output folder
        templates_folder: Path to templates folder
        meta_file_path: Path where metadata file should be saved
        drawing_slug: Drawing slug identifier
        output_drawing_type_folder: Output drawing type folder name
        version_folder: Version folder hint
        output_base_folder: Base output folder path
        
    Returns:
        Updated state
    """
    logger = services["logger"]
    
    final_status = state.get("final_status_dict")
    if not final_status or not final_status.get("success"):
        return state

    from processing.pipeline.paths import relative_to_output_root, iso_timestamp

    # structured_folder is now the drawing_folder (flattened layout)
    structured_section: Dict[str, Any] = {
        "directory": {
            "path": structured_folder,
            "relative_path": relative_to_output_root(structured_folder, output_base_folder),
        }
    }

    if os.path.exists(structured_output_path):
        structured_section["file"] = {
            "path": structured_output_path,
            "relative_path": relative_to_output_root(structured_output_path, output_base_folder),
            "size_bytes": os.path.getsize(structured_output_path),
            "updated_at": iso_timestamp(os.path.getmtime(structured_output_path)),
        }

    structured_archive = state.get("structured_document_info")
    if structured_archive:
        structured_section["archive"] = dict(structured_archive)

    template_entries = []
    for template_path in state.get("template_files", []) or []:
        if not template_path or not os.path.exists(template_path):
            continue
        template_entries.append(
            {
                "path": template_path,
                "relative_path": relative_to_output_root(template_path, output_base_folder),
                "size_bytes": os.path.getsize(template_path),
                "updated_at": iso_timestamp(os.path.getmtime(template_path)),
            }
        )

    metadata_payload = {
        "tenant_id": tenant_id,
        "drawing": {
            "slug": drawing_slug,
            "discipline": output_drawing_type_folder,
            "source_pdf": {
                "filename": file_name,
                "path": pdf_path,
            },
            "processed_at": iso_timestamp(),
            "pipeline_id": pipeline_id,
            "revision_hint": version_folder,
        },
        "structured_output": structured_section,
        "room_data": {
            "directory": {
                "path": templates_folder,  # Central room-data folder: output/room-data/<drawing_slug>/
                "relative_path": relative_to_output_root(templates_folder, output_base_folder),
            },
            "flags": dict(state.get("templates_created", {})),
            "files": template_entries,
        },
        "status": final_status.get("status"),
        "success": final_status.get("success", False),
    }

    source_info = state.get("source_document_info")
    if source_info:
        metadata_payload["source_document"] = dict(source_info)

    saved = await services["storage"].save_json(metadata_payload, meta_file_path)
    if saved:
        logger.info(f"Saved drawing metadata to {meta_file_path}")
    else:
        logger.error(f"Failed to save drawing metadata file for {file_name}")
    
    return state

