"""
Extraction service package for PDF content extraction.

This package provides modular extractors for different drawing types:
- Base PyMuPDF extraction
- Architectural drawings
- Electrical drawings (with panel schedule support)
- Mechanical drawings
- Plumbing drawings
"""
from .models import ExtractionResult
from .base import PdfExtractor, PyMuPdfExtractor
from .architectural import ArchitecturalExtractor
from .electrical import ElectricalExtractor
from .mechanical import MechanicalExtractor
from .plumbing import PlumbingExtractor
from .factory import create_extractor

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
