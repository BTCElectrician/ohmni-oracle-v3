"""
Custom exception classes for the Ohmni Oracle Template.
"""


class ExtractionError(Exception):
    """Raised when PDF extraction fails."""

    pass


class AIProcessingError(Exception):
    """Raised when the AI step fails."""

    pass


class JSONValidationError(Exception):
    """Raised when the JSON output is malformed."""

    pass


class MetadataValidationError(Exception):
    """Raised when drawing metadata fails validation."""

    pass


class FileSystemError(Exception):
    """Raised when file system operations fail."""

    pass
