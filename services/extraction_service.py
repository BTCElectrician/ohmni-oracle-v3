"""
Extraction service interface and implementations for PDF content extraction.

DEPRECATED: This module is maintained for backward compatibility.
New code should import from services.extraction instead.

This module re-exports all public APIs from services.extraction.
"""
import logging
import warnings

# Import all public APIs from the new package
from services.extraction import (
    ExtractionResult,
    PdfExtractor,
    PyMuPdfExtractor,
    ArchitecturalExtractor,
    ElectricalExtractor,
    MechanicalExtractor,
    PlumbingExtractor,
    create_extractor,
)

# Issue deprecation warning once per import
_warning_issued = False


def _issue_deprecation_warning():
    """Issue a one-time deprecation warning."""
    global _warning_issued
    if not _warning_issued:
        warnings.warn(
            "services.extraction_service is deprecated. "
            "Please use services.extraction instead.",
            DeprecationWarning,
            stacklevel=3,
        )
        _warning_issued = True


# Issue warning when module is imported
_issue_deprecation_warning()

# Re-export everything for backward compatibility
__all__ = [
    "ExtractionResult",
    "PdfExtractor",
    "PyMuPdfExtractor",
    "ArchitecturalExtractor",
    "ElectricalExtractor",
    "MechanicalExtractor",
    "PlumbingExtractor",
    "create_extractor",
]
