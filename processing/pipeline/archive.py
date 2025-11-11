"""
Archiving operations for the processing pipeline.

Handles archiving of original documents, structured output, and artifacts.
"""
import os
import time
from typing import Optional, Iterable, Dict, Any

from services.storage_service import StoredFileInfo, OriginalDocumentArchiver
from utils.exceptions import FileSystemError
from processing.pipeline.types import ProcessingState
from processing.pipeline.services import PipelineServices
from processing.pipeline.paths import (
    build_archive_storage_name,
    build_structured_storage_name,
    build_artifact_storage_name,
)


def attach_source_reference(
    state: ProcessingState,
    stored_info: StoredFileInfo,
    file_name: str,
) -> None:
    """Attach source document metadata to the parsed JSON payload.
    
    Note: Mutates state in place.
    
    Args:
        state: Processing state (mutated in place)
        stored_info: Stored file information
        file_name: Name of the PDF file
    """
    parsed_json = state.get("parsed_json_data")
    if not isinstance(parsed_json, dict):
        return

    source_document = {
        "uri": stored_info.get("uri"),
        "storage_name": stored_info.get("storage_name"),
        "filename": stored_info.get("filename", file_name),
        "size_bytes": stored_info.get("size_bytes"),
        "checksum_sha256": stored_info.get("checksum_sha256"),
        "content_type": stored_info.get("content_type"),
        "archived_at": time.time(),
    }

    if stored_info.get("path"):
        source_document["local_path"] = stored_info["path"]
    if stored_info.get("metadata"):
        source_document["storage_metadata"] = stored_info["metadata"]

    parsed_json["source_document"] = source_document


async def archive_structured_output(
    state: ProcessingState,
    services: PipelineServices,
    structured_output_path: str,
    file_name: str,
    pipeline_id: str,
    storage_discipline: str,
    drawing_slug: str,
) -> Optional[StoredFileInfo]:
    """Upload structured JSON output to configured archival storage (e.g., Azure Blob).
    
    Args:
        state: Processing state (mutated in place)
        services: Pipeline services bundle
        structured_output_path: Path to structured output file
        file_name: Name of the PDF file
        pipeline_id: Unique pipeline identifier
        storage_discipline: Storage discipline slug
        drawing_slug: Drawing slug identifier
        
    Returns:
        Stored file info if archiving succeeded, None otherwise
    """
    logger = services["logger"]
    structured_archiver = services["structured_archiver"]
    
    if not structured_archiver:
        return None

    if not os.path.exists(structured_output_path):
        logger.warning(
            "Structured output path %s missing when attempting archive",
            structured_output_path,
        )
        return None

    metadata = {
        "content_type": "application/json",
        "pipeline_id": pipeline_id,
        "drawing_type": state.get("processing_type_for_ai"),
        "original_pdf": file_name,
    }

    try:
        stored_info = await structured_archiver.archive(
            structured_output_path,
            storage_name=build_structured_storage_name(
                storage_discipline, drawing_slug, structured_output_path
            ),
            metadata=metadata,
            content_type="application/json",
        )
    except Exception as exc:
        logger.error(
            "Failed to archive structured output for %s: %s",
            file_name,
            exc,
            exc_info=True,
        )
        return None

    stored_info.setdefault("filename", os.path.basename(structured_output_path))
    stored_info.setdefault("content_type", "application/json")
    state["structured_document_info"] = stored_info
    logger.info(
        "Uploaded structured output to archival storage",
        extra={"blob_uri": stored_info.get("uri"), "storage_name": stored_info.get("storage_name")},
    )
    return stored_info


async def archive_original_document(
    state: ProcessingState,
    services: PipelineServices,
    pdf_path: str,
    file_name: str,
    pipeline_id: str,
    storage_discipline: str,
    drawing_slug: str,
) -> Optional[StoredFileInfo]:
    """Archive the original document if an archiver has been configured.
    
    Args:
        state: Processing state (mutated in place)
        services: Pipeline services bundle
        pdf_path: Path to the PDF file
        file_name: Name of the PDF file
        pipeline_id: Unique pipeline identifier
        storage_discipline: Storage discipline slug
        drawing_slug: Drawing slug identifier
        
    Returns:
        Stored file info if archiving succeeded, None otherwise
        
    Raises:
        FileSystemError: If archiving fails
    """
    logger = services["logger"]
    original_archiver = services["original_archiver"]
    
    if not original_archiver:
        logger.debug("Original document archive not configured; skipping upload")
        return None

    storage_name = build_archive_storage_name(storage_discipline, drawing_slug, file_name)
    metadata = {
        "content_type": "application/pdf",
        "pipeline_id": pipeline_id,
        "drawing_type": state.get("processing_type_for_ai"),
        "original_filename": file_name,
    }

    try:
        stored_info = await original_archiver.archive(
            pdf_path,
            storage_name=storage_name,
            metadata=metadata,
            content_type="application/pdf",
        )
    except Exception as exc:
        logger.error(
            f"Failed to archive original document for {file_name}: {exc}",
            exc_info=True,
        )
        raise FileSystemError(f"Failed to archive original document: {exc}") from exc

    stored_info.setdefault("filename", file_name)
    stored_info.setdefault("size_bytes", os.path.getsize(pdf_path))
    state["source_document_info"] = stored_info
    return stored_info


async def archive_additional_artifacts(
    services: PipelineServices,
    file_paths: Iterable[str],
    file_name: str,
    pipeline_id: str,
    storage_discipline: str,
    drawing_slug: str,
    *,
    artifact_type: str,
    content_type: str = "application/json",
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Upload additional artifacts related to the drawing (e.g., room templates).
    
    Args:
        services: Pipeline services bundle
        file_paths: Iterable of artifact file paths
        file_name: Name of the PDF file
        pipeline_id: Unique pipeline identifier
        storage_discipline: Storage discipline slug
        drawing_slug: Drawing slug identifier
        artifact_type: Type of artifact (e.g., "templates")
        content_type: MIME content type for artifacts
    """
    logger = services["logger"]
    structured_archiver = services["structured_archiver"]
    
    if not structured_archiver:
        return

    for artifact_path in file_paths:
        if not artifact_path or not os.path.exists(artifact_path):
            continue

        metadata = {
            "content_type": content_type,
            "pipeline_id": pipeline_id,
            "artifact_type": artifact_type,
            "original_pdf": file_name,
        }
        if extra_metadata:
            metadata.update(extra_metadata)

        storage_name = build_artifact_storage_name(
            storage_discipline, drawing_slug, os.path.basename(artifact_path), artifact_type
        )

        try:
            await structured_archiver.archive(
                artifact_path,
                storage_name=storage_name,
                metadata=metadata,
                content_type=content_type,
            )
            logger.info(
                "Uploaded %s artifact to archival storage",
                artifact_type,
                extra={
                    "artifact_path": artifact_path,
                    "storage_name": storage_name,
                },
            )
        except Exception as exc:
            logger.error(
                "Failed to archive %s artifact %s: %s",
                artifact_type,
                artifact_path,
                exc,
            )

