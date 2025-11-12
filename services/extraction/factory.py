"""
Factory function for creating appropriate extractors based on drawing type.
"""
import logging
from typing import Optional

from .base import PyMuPdfExtractor, PdfExtractor
from .architectural import ArchitecturalExtractor
from .electrical import ElectricalExtractor
from .mechanical import MechanicalExtractor
from .plumbing import PlumbingExtractor


def create_extractor(
    drawing_type: str, logger: Optional[logging.Logger] = None
) -> PdfExtractor:
    """
    Factory function to create the appropriate extractor based on drawing type.

    Args:
        drawing_type: Type of drawing (Architectural, Electrical, etc.)
        logger: Optional logger instance

    Returns:
        Appropriate PdfExtractor implementation
    """
    drawing_type = drawing_type.lower() if drawing_type else ""

    if "architectural" in drawing_type:
        return ArchitecturalExtractor(logger)
    elif "electrical" in drawing_type:
        return ElectricalExtractor(logger)
    elif "mechanical" in drawing_type:
        return MechanicalExtractor(logger)
    elif "plumbing" in drawing_type:
        return PlumbingExtractor(logger)
    else:
        # Default to the base extractor for other types
        return PyMuPdfExtractor(logger)

