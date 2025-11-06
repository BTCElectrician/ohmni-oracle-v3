"""
Storage service interface and implementations for saving processing results.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TypedDict
import os
import json
import logging
import aiofiles
import datetime  # Add this import for date/datetime handling
import hashlib
import mimetypes
from pathlib import Path


class StorageService(ABC):
    """
    Abstract base class defining the interface for storage services.
    """

    @abstractmethod
    async def save_json(self, data: Dict[str, Any], file_path: str) -> bool:
        """
        Save JSON data to a file.

        Args:
            data: JSON-serializable data to save
            file_path: Path where the file should be saved

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def save_text(self, text: str, file_path: str) -> bool:
        """
        Save text data to a file.

        Args:
            text: Text content to save
            file_path: Path where the file should be saved

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def save_binary(self, data: bytes, file_path: str) -> bool:
        """
        Save binary data to a file.

        Args:
            data: Binary content to save
            file_path: Path where the file should be saved

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def read_json(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Read JSON data from a file.

        Args:
            file_path: Path to the file to read

        Returns:
            Parsed JSON data if successful, None otherwise
        """
        pass


class FileSystemStorage(StorageService):
    """
    Storage service implementation using the local file system.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

    async def save_json(self, data: Dict[str, Any], file_path: str) -> bool:
        """
        Save JSON data to a file with support for date objects.

        Args:
            data: JSON-serializable data to save
            file_path: Path where the file should be saved

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Import the DateTimeEncoder here to avoid circular imports
            from utils.json_utils import DateTimeEncoder

            # Save the file asynchronously with custom encoder
            async with aiofiles.open(file_path, "w") as f:
                json_str = json.dumps(data, indent=2, cls=DateTimeEncoder)
                await f.write(json_str)

            self.logger.info(f"Successfully saved JSON to {file_path}")
            return True
        except TypeError as e:
            # Specific handling for JSON serialization errors
            if "not JSON serializable" in str(e):
                self.logger.error(f"JSON serialization error in {file_path}: {str(e)}")
                # Try to identify problematic fields
                problematic_keys = []
                for key, value in data.items():
                    if isinstance(value, (datetime.date, datetime.datetime)):
                        problematic_keys.append(key)
                if problematic_keys:
                    self.logger.error(
                        f"Fields containing date objects: {problematic_keys}"
                    )
            self.logger.error(f"Error saving JSON to {file_path}: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Error saving JSON to {file_path}: {str(e)}")
            return False

    async def save_text(self, text: str, file_path: str) -> bool:
        """
        Save text data to a file.

        Args:
            text: Text content to save
            file_path: Path where the file should be saved

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Save the file asynchronously
            async with aiofiles.open(file_path, "w") as f:
                await f.write(text)

            self.logger.info(f"Successfully saved text to {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving text to {file_path}: {str(e)}")
            return False

    async def save_binary(self, data: bytes, file_path: str) -> bool:
        """
        Save binary data to a file.

        Args:
            data: Binary content to save
            file_path: Path where the file should be saved

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Save the file asynchronously
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(data)

            self.logger.info(f"Successfully saved binary data to {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving binary data to {file_path}: {str(e)}")
            return False

    async def read_json(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Read JSON data from a file.

        Args:
            file_path: Path to the file to read

        Returns:
            Parsed JSON data if successful, None otherwise
        """
        try:
            if not os.path.exists(file_path):
                self.logger.warning(f"File not found: {file_path}")
                return None

            # Read the file asynchronously
            async with aiofiles.open(file_path, "r") as f:
                content = await f.read()

            # Parse JSON
            data = json.loads(content)
            self.logger.info(f"Successfully read JSON from {file_path}")
            return data
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing JSON from {file_path}: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Error reading JSON from {file_path}: {str(e)}")
            return None


_CUSTOM_CONTENT_TYPES = {
    ".dwg": "application/acad",
    ".dxf": "application/dxf",
    ".rvt": "application/octet-stream",
}


def _detect_content_type(file_path: str, default: str = "application/octet-stream") -> str:
    """Best-effort MIME type detection with construction drawing defaults."""
    mime, _ = mimetypes.guess_type(file_path)
    if mime:
        return mime

    suffix = Path(file_path).suffix.lower()
    return _CUSTOM_CONTENT_TYPES.get(suffix, default)


class StoredFileInfo(TypedDict, total=False):
    """Details about a stored source document."""

    uri: str
    storage_name: str
    path: str
    filename: str
    size_bytes: int
    checksum_sha256: str
    content_type: str
    metadata: Dict[str, Any]


class OriginalDocumentArchiver(ABC):
    """Interface for archiving original drawing files to retrievable storage."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def archive(
        self,
        source_path: str,
        storage_name: Optional[str] = None,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        content_type: Optional[str] = None,
    ) -> StoredFileInfo:
        """Persist the original document and return retrieval metadata."""
        raise NotImplementedError


class LocalDocumentArchiver(OriginalDocumentArchiver):
    """Archives source documents to a local folder structure."""

    def __init__(self, base_folder: str, logger: Optional[logging.Logger] = None):
        super().__init__(logger)
        self.base_folder = os.path.abspath(base_folder)
        os.makedirs(self.base_folder, exist_ok=True)

    async def archive(
        self,
        source_path: str,
        storage_name: Optional[str] = None,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        content_type: Optional[str] = None,
    ) -> StoredFileInfo:
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source file not found for archival: {source_path}")

        relative_name = storage_name or os.path.basename(source_path)
        normalized_relative = os.path.normpath(relative_name).lstrip(os.sep)

        if normalized_relative.startswith("..") or ".." in Path(normalized_relative).parts:
            raise ValueError("Storage name cannot traverse outside the archive root")

        destination_path = os.path.normpath(os.path.join(self.base_folder, normalized_relative))
        base_root = self.base_folder
        if os.path.commonpath([destination_path, base_root]) != base_root:
            raise ValueError("Storage path resolved outside of archive root")

        destination_dir = os.path.dirname(destination_path)
        os.makedirs(destination_dir, exist_ok=True)

        async with aiofiles.open(source_path, "rb") as source_file, aiofiles.open(
            destination_path, "wb"
        ) as destination_file:
            while True:
                chunk = await source_file.read(1024 * 1024)
                if not chunk:
                    break
                await destination_file.write(chunk)

        size_bytes = os.path.getsize(destination_path)
        # Reuse checksum if provided; otherwise compute lazily for integrity checks
        checksum = metadata.get("checksum_sha256") if metadata else None
        if not checksum:
            hash_calculator = hashlib.sha256()
            async with aiofiles.open(destination_path, "rb") as stored_file:
                while True:
                    chunk = await stored_file.read(1024 * 1024)
                    if not chunk:
                        break
                    hash_calculator.update(chunk)
            checksum = hash_calculator.hexdigest()

        detected_content_type = _detect_content_type(source_path, default="application/pdf")
        resolved_content_type = (
            content_type
            or (metadata.get("content_type") if metadata else None)
            or detected_content_type
        )

        result: StoredFileInfo = {
            "uri": destination_path,
            "storage_name": relative_name.replace(os.sep, "/"),
            "path": destination_path,
            "filename": os.path.basename(source_path),
            "size_bytes": size_bytes,
            "checksum_sha256": checksum,
            "content_type": resolved_content_type,
        }

        combined_metadata = dict(metadata or {})
        combined_metadata.setdefault("content_type", resolved_content_type)
        combined_metadata.setdefault("checksum_sha256", checksum)

        if combined_metadata:
            result["metadata"] = combined_metadata

        self.logger.info(
            "Archived original document locally",
            extra={"storage_name": result["storage_name"], "size_bytes": size_bytes},
        )

        return result


class AzureBlobDocumentArchiver(OriginalDocumentArchiver):
    """Archives source documents to Azure Blob Storage for retrieval."""

    def __init__(
        self,
        *,
        container_name: str,
        prefix: str = "",
        connection_string: Optional[str] = None,
        account_url: Optional[str] = None,
        credential: Optional[str] = None,
        sas_token: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        super().__init__(logger)

        try:
            from azure.storage.blob.aio import BlobServiceClient
        except ImportError as exc:  # pragma: no cover - depends on optional package
            raise RuntimeError(
                "azure-storage-blob must be installed to archive originals to Azure Blob Storage"
            ) from exc

        if connection_string:
            self._service_client = BlobServiceClient.from_connection_string(connection_string)
        elif account_url:
            if sas_token:
                account_url = f"{account_url.rstrip('?')}?{sas_token.lstrip('?')}"
                self._service_client = BlobServiceClient(account_url)
            elif credential:
                self._service_client = BlobServiceClient(account_url=account_url, credential=credential)
            else:
                raise ValueError(
                    "Azure Blob archival requires either a connection string, SAS token, or credential with the account URL"
                )
        else:
            raise ValueError("Azure Blob archival requires connection details")

        self._container_client = self._service_client.get_container_client(container_name)
        self._prefix = prefix.strip("/") if prefix else ""
        self._container_created = False

    async def _ensure_container(self) -> None:
        if self._container_created:
            return
        try:
            from azure.core.exceptions import ResourceExistsError

            await self._container_client.create_container()
        except ResourceExistsError:  # Container already exists
            pass
        self._container_created = True

    async def archive(
        self,
        source_path: str,
        storage_name: Optional[str] = None,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        content_type: Optional[str] = None,
    ) -> StoredFileInfo:
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source file not found for archival: {source_path}")

        await self._ensure_container()

        requested_name = storage_name or os.path.basename(source_path)
        normalized_name = os.path.normpath(requested_name).replace("\\", "/")
        if normalized_name.startswith(".."):  # quick reject for traversal
            raise ValueError("Storage name cannot traverse outside the container prefix")
        if ".." in Path(normalized_name).parts:
            raise ValueError("Storage name cannot include parent directory segments")

        blob_name_parts = [part for part in [self._prefix, normalized_name] if part]
        blob_name = "/".join(blob_name_parts)

        from azure.storage.blob import ContentSettings  # type: ignore

        blob_client = self._container_client.get_blob_client(blob_name)

        size_bytes = os.path.getsize(source_path)

        hasher = hashlib.sha256()
        async with aiofiles.open(source_path, "rb") as source_file:
            while True:
                chunk = await source_file.read(4 * 1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)

        checksum = hasher.hexdigest()
        detected_content_type = _detect_content_type(source_path, default="application/octet-stream")
        resolved_content_type = (
            content_type
            or (metadata.get("content_type") if metadata else None)
            or detected_content_type
        )

        # Azure requires metadata values to be strings
        azure_metadata = {k: str(v) for k, v in (metadata or {}).items()}
        azure_metadata.setdefault("checksum_sha256", checksum)
        azure_metadata.setdefault("filename", os.path.basename(source_path))
        azure_metadata.setdefault("content_type", resolved_content_type)

        async def chunk_reader():
            async with aiofiles.open(source_path, "rb") as upload_file:
                while True:
                    chunk = await upload_file.read(4 * 1024 * 1024)
                    if not chunk:
                        break
                    yield chunk

        await blob_client.upload_blob(
            chunk_reader(),
            length=size_bytes,
            overwrite=True,
            metadata=azure_metadata or None,
            content_settings=ContentSettings(content_type=resolved_content_type),
            max_concurrency=1,
        )

        result: StoredFileInfo = {
            "uri": blob_client.url,
            "storage_name": blob_name,
            "filename": os.path.basename(source_path),
            "size_bytes": size_bytes,
            "checksum_sha256": checksum,
            "content_type": resolved_content_type,
        }

        combined_metadata = dict(metadata or {})
        combined_metadata.setdefault("content_type", resolved_content_type)
        combined_metadata.setdefault("checksum_sha256", checksum)

        if combined_metadata:
            result["metadata"] = combined_metadata

        self.logger.info(
            "Archived original document to Azure Blob Storage",
            extra={"storage_name": blob_name, "size_bytes": size_bytes},
        )

        return result
