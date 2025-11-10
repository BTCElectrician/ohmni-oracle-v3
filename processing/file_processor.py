# processing/file_processor.py
"""
Thin adapter layer for backward compatibility.

This module maintains the public API (FileProcessingPipeline class and
process_pdf_async function) while delegating to the modular pipeline
implementation in processing.pipeline.
"""
import os
import logging
from typing import Dict, Any, Optional, cast

from openai import AsyncOpenAI
from pydantic import validate_call

from services.storage_service import (
    FileSystemStorage,
    OriginalDocumentArchiver,
    LocalDocumentArchiver,
    AzureBlobDocumentArchiver,
    StoredFileInfo,
)
from utils.storage_utils import derive_drawing_identifiers
from config.settings import (
    ORIGINAL_STORAGE_BACKEND,
    ORIGINAL_STORAGE_PREFIX,
    AZURE_BLOB_CONNECTION_STRING,
    AZURE_BLOB_ACCOUNT_URL,
    AZURE_BLOB_CREDENTIAL,
    AZURE_BLOB_SAS_TOKEN,
    AZURE_BLOB_CONTAINER,
    STRUCTURED_STORAGE_BACKEND,
    STRUCTURED_STORAGE_PREFIX,
    STRUCTURED_BLOB_CONNECTION_STRING,
    STRUCTURED_BLOB_ACCOUNT_URL,
    STRUCTURED_BLOB_CREDENTIAL,
    STRUCTURED_BLOB_SAS_TOKEN,
    STRUCTURED_BLOB_CONTAINER,
)

# Re-export types for backward compatibility
from processing.pipeline.types import ProcessingStatus, ProcessingState, ProcessingResult
from processing.pipeline.services import PipelineServices
from processing.pipeline.orchestrator import process_pipeline
from processing.pipeline.status import save_status_file


def is_panel_schedule(file_name: str, subtype: str) -> bool:
    """
    Determine if a file is a panel schedule based on filename and subtype.
    
    This function is maintained for backward compatibility with tests.
    
    Args:
        file_name: Name of the PDF file
        subtype: Subtype string (currently unused but kept for API compatibility)
        
    Returns:
        True if the file appears to be a panel schedule
    """
    return "panel" in file_name.lower() or "panel" in (subtype or "").lower()


class FileProcessingPipeline:
    """
    Processes a PDF file through a series of extraction, AI processing, 
    and normalization steps to produce structured data.
    
    This class is a thin adapter that delegates to the modular pipeline
    implementation. It maintains backward compatibility with existing code.
    
    Note: This class is maintained for backward compatibility. New code
    should consider using processing.pipeline.orchestrator.process_pipeline
    directly.
    """

    def __init__(
        self,
        pdf_path: str,
        client: AsyncOpenAI,
        output_folder: str,
        drawing_type: str,
        templates_created: Dict[str, bool],
        storage: FileSystemStorage,
        logger: logging.Logger,
        original_archiver: Optional[OriginalDocumentArchiver] = None,
        structured_archiver: Optional[OriginalDocumentArchiver] = None,
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
            original_archiver: Optional service for archiving original documents
            structured_archiver: Optional service for archiving structured JSON output
        """
        self.pdf_path = pdf_path
        self.client = client
        self.output_folder = output_folder
        self.drawing_type = drawing_type
        self.templates_created = templates_created
        self.storage = storage
        self.logger = logger
        self.original_archiver = original_archiver
        self.structured_archiver = structured_archiver

    async def process(self) -> ProcessingResult:
        """
        Process the PDF file through the complete pipeline.
        
        Returns:
            Dictionary with processing results
        """
        services: PipelineServices = {
            "client": self.client,
            "storage": self.storage,
            "logger": self.logger,
            "original_archiver": self.original_archiver,
            "structured_archiver": self.structured_archiver,
        }
        
        return await process_pipeline(
            self.pdf_path,
            services,
            self.output_folder,
            self.drawing_type,
            self.templates_created,
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

    original_archiver: Optional[OriginalDocumentArchiver] = None
    structured_archiver: Optional[OriginalDocumentArchiver] = None
    backend = (ORIGINAL_STORAGE_BACKEND or "filesystem").lower()
    structured_backend = (STRUCTURED_STORAGE_BACKEND or "").lower()
    if structured_backend in ("", "auto", "inherit"):
        structured_backend = backend

    try:
        if backend in ("filesystem", "local"):
            archive_root = os.path.join(output_folder, ORIGINAL_STORAGE_PREFIX or "source-documents")
            original_archiver = LocalDocumentArchiver(archive_root, logger=logger_instance)
        elif backend in ("azure", "azure_blob", "azureblob"):
            if not (AZURE_BLOB_CONNECTION_STRING or AZURE_BLOB_ACCOUNT_URL):
                raise ValueError("Azure Blob archival selected, but no connection string or account URL provided")
            original_archiver = AzureBlobDocumentArchiver(
                container_name=AZURE_BLOB_CONTAINER,
                prefix=ORIGINAL_STORAGE_PREFIX,
                connection_string=AZURE_BLOB_CONNECTION_STRING,
                account_url=AZURE_BLOB_ACCOUNT_URL,
                credential=AZURE_BLOB_CREDENTIAL,
                sas_token=AZURE_BLOB_SAS_TOKEN,
                logger=logger_instance,
            )
        elif backend in ("none", "disabled"):
            logger_instance.info("Original document archival disabled via configuration")
            original_archiver = None
        else:
            logger_instance.warning(
                "Unknown ORIGINAL_STORAGE_BACKEND '%s' - falling back to filesystem archival",
                backend,
            )
            archive_root = os.path.join(output_folder, ORIGINAL_STORAGE_PREFIX or "source-documents")
            original_archiver = LocalDocumentArchiver(archive_root, logger=logger_instance)
    except Exception as exc:
        logger_instance.error(f"Failed to initialize original document archiver: {exc}")
        raise

    try:
        if structured_backend in ("azure", "azure_blob", "azureblob"):
            if not (STRUCTURED_BLOB_CONNECTION_STRING or STRUCTURED_BLOB_ACCOUNT_URL):
                raise ValueError(
                    "Structured output archival set to Azure, but no connection string or account URL provided"
                )
            structured_archiver = AzureBlobDocumentArchiver(
                container_name=STRUCTURED_BLOB_CONTAINER or AZURE_BLOB_CONTAINER,
                prefix=STRUCTURED_STORAGE_PREFIX,
                connection_string=STRUCTURED_BLOB_CONNECTION_STRING or AZURE_BLOB_CONNECTION_STRING,
                account_url=STRUCTURED_BLOB_ACCOUNT_URL or AZURE_BLOB_ACCOUNT_URL,
                credential=STRUCTURED_BLOB_CREDENTIAL or AZURE_BLOB_CREDENTIAL,
                sas_token=STRUCTURED_BLOB_SAS_TOKEN or AZURE_BLOB_SAS_TOKEN,
                logger=logger_instance,
            )
        elif structured_backend in ("none", "disabled", "off", ""):
            structured_archiver = None
        # Filesystem/local storage already handled by FileSystemStorage save step
    except Exception as exc:
        logger_instance.error(f"Failed to initialize structured output archiver: {exc}")
        raise
    
    try:
        pipeline = FileProcessingPipeline(
            pdf_path,
            client,
            output_folder,
            drawing_type,
            templates_created,
            storage,
            logger_instance,
            original_archiver=original_archiver,
            structured_archiver=structured_archiver,
        )
        return await pipeline.process()
    except Exception as e:
        # Catch-all for unexpected errors
        logger_instance.error(f"Unexpected error processing {pdf_path}: {str(e)}", exc_info=True)
        
        # Create error output path
        filename_base = os.path.splitext(os.path.basename(pdf_path))[0]
        output_type_folder = drawing_type if drawing_type else "General"
        type_folder = os.path.join(output_folder, output_type_folder)
        drawing_slug, _ = derive_drawing_identifiers(os.path.basename(pdf_path))
        drawing_folder = os.path.join(type_folder, drawing_slug)
        os.makedirs(drawing_folder, exist_ok=True)
        error_output_path = os.path.join(drawing_folder, f"{filename_base}_error.json")
        
        # Save error status
        await save_status_file(
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
            "source_document": None,
            "structured_document": None,
        }
    finally:
        for archiver in (original_archiver, structured_archiver):
            if not archiver:
                continue
            try:
                await archiver.close()
            except Exception as exc:  # pragma: no cover - best-effort cleanup
                logger_instance.warning(f"Failed to close archiver: {exc}")
