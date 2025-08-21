"""
Storage service interface and implementations for saving processing results.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import os
import json
import logging
import aiofiles
import datetime  # Add this import for date/datetime handling


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
