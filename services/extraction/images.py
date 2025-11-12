"""
Page-to-image conversion utilities.
"""
import os
import logging
from typing import Optional

import pymupdf as fitz


def save_page_as_image_sync(
    file_path: str,
    page_num: int,
    output_path: str,
    dpi: int = 300,
    logger: Optional[logging.Logger] = None,
) -> str:
    """
    Internal method to save a PDF page as an image.
    This method runs synchronously (typically in an executor).

    Args:
        file_path: Path to the PDF file
        page_num: Page number to extract (0-based)
        output_path: Path to save the image
        dpi: DPI for the rendered image
        logger: Optional logger instance

    Returns:
        Path to the saved image

    Raises:
        FileNotFoundError: If the file does not exist
        IndexError: If the page number is out of range
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        raise FileNotFoundError(f"File not found: {file_path}")

    with fitz.open(file_path) as doc:
        if page_num < 0 or page_num >= len(doc):
            raise IndexError(f"Page number {page_num} out of range (0-{len(doc)-1})")

        page = doc[page_num]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
        pixmap.save(output_path)

        logger.info(f"Saved page {page_num} as image: {output_path}")
        return output_path

