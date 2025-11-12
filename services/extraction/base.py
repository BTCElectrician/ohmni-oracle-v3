"""
Base PDF extractor implementation using PyMuPDF.
"""
import os
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple

import pymupdf as fitz

from utils.performance_utils import time_operation, time_operation_context
from utils.drawing_utils import detect_drawing_info

from .models import ExtractionResult
from .titleblock import extract_titleblock_region_text
from .tables import extract_tables_for_page
from .images import save_page_as_image_sync


class PdfExtractor(ABC):
    """
    Abstract base class defining the interface for PDF extraction services.
    """

    @abstractmethod
    async def extract(self, file_path: str) -> ExtractionResult:
        """
        Extract content from a PDF file.

        Args:
            file_path: Path to the PDF file

        Returns:
            ExtractionResult containing the extracted content
        """
        pass


class PyMuPdfExtractor(PdfExtractor):
    """
    PDF content extractor implementation using PyMuPDF.
    """

    def __init__(
        self, logger: Optional[logging.Logger] = None, min_content_length: int = 50
    ):
        self.logger = logger or logging.getLogger(__name__)
        self.min_content_length = min_content_length

    def _extract_content(
        self, file_path: str
    ) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any], str]:
        """
        Internal method to extract content from a PDF file.
        This method runs in a separate thread.

        Args:
            file_path: Path to the PDF file

        Returns:
            Tuple of (raw_text, tables, metadata, titleblock_text)
        """
        # Use context manager to ensure document is properly closed
        with fitz.open(file_path) as doc:
            # Extract metadata first
            metadata = {
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
                "subject": doc.metadata.get("subject", ""),
                "creator": doc.metadata.get("creator", ""),
                "producer": doc.metadata.get("producer", ""),
                "creation_date": doc.metadata.get("creationDate", ""),
                "modification_date": doc.metadata.get("modDate", ""),
                "page_count": len(doc),
            }

            # Initialize containers for text and tables
            raw_text = ""
            tables = []
            titleblock_text = ""

            # Extract title block text from the first page (if pages exist)
            if len(doc) > 0:
                titleblock_text = extract_titleblock_region_text(
                    doc, page_num=0, logger=self.logger
                )
                if titleblock_text:
                    self.logger.info(
                        f"Extracted {len(titleblock_text)} chars from title block"
                    )

            # Process each page individually to avoid reference issues
            enable_table_extraction = (
                os.getenv("ENABLE_TABLE_EXTRACTION", "true").lower() == "true"
            )
            table_notice_logged = False
            for i, page in enumerate(doc):
                # Add page header
                page_text = f"PAGE {i+1}:\n"

                # Try block-based extraction first
                try:
                    blocks = page.get_text("blocks")
                    for block in blocks:
                        if block[6] == 0:  # Text block (type 0)
                            page_text += block[4] + "\n"
                except Exception as e:
                    self.logger.warning(
                        f"Block extraction error on page {i+1} of {os.path.basename(file_path)}: {str(e)}"
                    )
                    # Fall back to regular text extraction
                    try:
                        page_text += page.get_text() + "\n\n"
                    except Exception as e2:
                        self.logger.warning(
                            f"Error extracting text from page {i+1}: {str(e2)}"
                        )
                        page_text += "[Error extracting text from this page]\n\n"

                # Add to overall text
                raw_text += page_text

                # Extract tables safely (ONLY if enabled)
                page_tables = extract_tables_for_page(
                    page, i + 1, enable_table_extraction, logger=self.logger
                )
                tables.extend(page_tables)

                if not enable_table_extraction and not table_notice_logged:
                    self.logger.info(
                        "ENABLE_TABLE_EXTRACTION=false; skipping PyMuPDF table detection for speed"
                    )
                    table_notice_logged = True

            return raw_text, tables, metadata, titleblock_text

    @time_operation("extraction")
    async def extract(self, file_path: str) -> ExtractionResult:
        """
        Extract text and tables from a PDF file using PyMuPDF.
        Checks if extracted text meets a minimum length threshold.

        Args:
            file_path: Path to the PDF file

        Returns:
            ExtractionResult containing the extracted content and status flags
        """
        try:
            self.logger.info(f"Starting extraction for {file_path}")

            # Use run_in_executor to move CPU-bound work off the main thread
            loop = asyncio.get_event_loop()

            # Determine drawing type for tracking (using filename detection)
            main_type, _ = detect_drawing_info(file_path)
            detected_drawing_type = main_type

            with time_operation_context(
                "extraction_pdf_read",
                file_path=file_path,
                drawing_type=detected_drawing_type,
            ):
                raw_text, tables, metadata, titleblock_text = await loop.run_in_executor(
                    None, self._extract_content, file_path
                )

            # Strip whitespace and check length against the threshold
            meaningful_text = raw_text.strip() if raw_text else ""
            has_content = len(meaningful_text) >= self.min_content_length

            if not has_content:
                # Log clearly if no significant content was found
                self.logger.warning(
                    f"No significant machine-readable content extracted (length < {self.min_content_length}) from {file_path}"
                )
                # Still consider extraction successful, but flag lack of content
                return ExtractionResult(
                    raw_text=raw_text,
                    tables=tables,
                    success=True,
                    has_content=False,
                    error="No significant machine-readable content found.",
                    metadata=metadata,
                    titleblock_text=titleblock_text,
                )

            self.logger.info(f"Successfully extracted content from {file_path}")
            return ExtractionResult(
                raw_text=raw_text,
                tables=tables,
                success=True,
                has_content=True,
                metadata=metadata,
                titleblock_text=titleblock_text,
            )
        except Exception as e:
            self.logger.error(f"Error extracting content from {file_path}: {str(e)}")
            return ExtractionResult(
                raw_text="",
                tables=[],
                success=False,
                has_content=False,
                error=str(e),
                metadata={},
                titleblock_text=None,
            )

    async def save_page_as_image(
        self, file_path: str, page_num: int, output_path: str, dpi: int = 300
    ) -> str:
        """
        Save a PDF page as an image.

        Args:
            file_path: Path to the PDF file
            page_num: Page number to extract (0-based)
            output_path: Path to save the image
            dpi: DPI for the rendered image (default: 300)

        Returns:
            Path to the saved image

        Raises:
            FileNotFoundError: If the file does not exist
            IndexError: If the page number is out of range
            Exception: For any other errors during extraction
        """
        try:
            if not os.path.exists(file_path):
                self.logger.error(f"File not found: {file_path}")
                raise FileNotFoundError(f"File not found: {file_path}")

            # Use run_in_executor to move CPU-bound work off the main thread
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                save_page_as_image_sync,
                file_path,
                page_num,
                output_path,
                dpi,
                self.logger,
            )

            return result
        except Exception as e:
            self.logger.error(f"Error saving page as image: {str(e)}")
            raise

