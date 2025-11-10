"""
Status file management for the processing pipeline.
"""
import logging
import time

from services.storage_service import FileSystemStorage
from utils.exceptions import FileSystemError


async def save_status_file(
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
        saved = await storage.save_json(status_data, file_path)
        if not saved:
            raise FileSystemError(f"Storage backend reported failure saving status file {file_path}")
        logging.getLogger(__name__).info(f"Saved status file ({status}) to: {file_path}")
    except Exception as e:
        logging.getLogger(__name__).error(
            "Failed to save status file",
            extra={"file_path": file_path, "status": status, "error": str(e)},
        )
        raise FileSystemError(f"Failed to save status file {file_path}: {e}") from e

