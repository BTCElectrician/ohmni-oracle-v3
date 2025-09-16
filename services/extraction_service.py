"""
Extraction service interface and implementations for PDF content extraction.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
import logging
import asyncio
import os
import re

import pymupdf as fitz

from utils.performance_utils import time_operation, time_operation_context
from utils.drawing_utils import detect_drawing_info


class ExtractionResult:
    """
    Domain model representing the result of a PDF extraction operation.
    Includes a flag to indicate if meaningful content was extracted.
    """

    def __init__(
        self,
        raw_text: str,
        tables: List[Dict[str, Any]],
        success: bool,
        has_content: bool,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        titleblock_text: Optional[str] = None,
    ):
        self.raw_text = raw_text
        self.tables = tables
        self.success = success
        self.has_content = has_content
        self.error = error
        self.metadata = metadata or {}
        self.titleblock_text = titleblock_text

    def to_dict(self) -> Dict[str, Any]:
        """Convert the result to a dictionary."""
        return {
            "raw_text": self.raw_text,
            "tables": self.tables,
            "success": self.success,
            "has_content": self.has_content,
            "error": self.error,
            "metadata": self.metadata,
            "titleblock_text": self.titleblock_text,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtractionResult":
        """Create an ExtractionResult from a dictionary."""
        return cls(
            raw_text=data.get("raw_text", ""),
            tables=data.get("tables", []),
            success=data.get("success", False),
            has_content=data.get("has_content", False),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
            titleblock_text=data.get("titleblock_text"),
        )


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

    def _extract_titleblock_region_text(self, doc: fitz.Document, page_num: int) -> str:
        """
        Extract title block with progressive expansion if truncated.
        Handles rotated pages and various title block positions.
        """
        if page_num < 0 or page_num >= len(doc):
            self.logger.warning(f"Page number {page_num} out of range (0-{len(doc)-1})")
            return ""

        page = doc[page_num]
        page_rect = page.rect
        
        # Handle page rotation
        rotation = page.rotation
        is_rotated = rotation in (90, 270)
        
        # Define search regions based on orientation
        # Format: (x0_pct, y0_pct, x1_pct, y1_pct, name)
        if is_rotated:
            regions = [
                (0.00, 0.70, 0.30, 1.00, "left_strip"),     # Left strip for rotated
                (0.70, 0.60, 1.00, 1.00, "bottom_right"),   # Adjusted bottom-right
            ]
        else:
            regions = [
                (0.70, 0.00, 1.00, 1.00, "right_strip"),    # Right vertical strip
                (0.60, 0.70, 1.00, 1.00, "bottom_right"),   # Bottom-right corner
                (0.00, 0.85, 1.00, 1.00, "bottom_strip"),   # Bottom horizontal strip
            ]
        
        best_text = ""
        best_score = 0.0
        best_region_name = ""
        
        for x0_pct, y0_pct, x1_pct, y1_pct, region_name in regions:
            # Try progressively larger regions if we need to expand leftward
            expansions = [0.0]
            if x0_pct > 0.5:  # Only expand regions that start from right side
                expansions.extend([0.10, 0.20])
            
            for expansion in expansions:
                # Apply expansion
                x0_expanded = max(0, x0_pct - expansion)
                
                # Create extraction rectangle
                rect = fitz.Rect(
                    page_rect.width * x0_expanded,
                    page_rect.height * y0_pct,
                    page_rect.width * x1_pct,
                    page_rect.height * y1_pct
                )
                
                # Extract text from region
                try:
                    text = page.get_text("text", clip=rect).strip()
                except Exception as e:
                    self.logger.warning(f"Error extracting from region {region_name}: {e}")
                    continue
                
                if not text or len(text) < 50:
                    continue
                
                # Score the extracted text
                score = self._score_titleblock_text(text)
                
                # Check if this is our best candidate so far
                if score > best_score:
                    best_text = text
                    best_score = score
                    best_region_name = f"{region_name}_exp{int(expansion*100)}"
                
                # Early exit if we found high-quality, non-truncated text
                if score >= 0.8 and not self._looks_truncated(text):
                    self.logger.info(
                        f"High-quality title block found in {region_name} "
                        f"(expansion: {int(expansion*100)}%, "
                        f"chars: {len(text)}, score: {score:.2f})"
                    )
                    return text
                
                # If text looks truncated and we can expand more, continue
                if self._looks_truncated(text) and expansion < 0.20:
                    continue
                    
        # Log what we found
        if best_text:
            self.logger.info(
                f"Best title block from {best_region_name}: "
                f"{len(best_text)} chars, score: {best_score:.2f}, "
                f"truncated: {self._looks_truncated(best_text)}"
            )
        else:
            self.logger.warning(f"No title block found on page {page_num}")
        
        return best_text

    def _score_titleblock_text(self, text: str) -> float:
        """
        Score text likelihood of being a title block (0.0-1.0).
        Higher scores indicate more confidence it's a title block.
        """
        if not text:
            return 0.0
        
        score = 0.0
        text_upper = text.upper()
        
        # Keywords commonly found in title blocks with their weights
        keywords = {
            'PROJECT': 0.25,
            'SHEET': 0.15,
            'DRAWING': 0.10,
            'DATE': 0.10,
            'DRAWN': 0.10,
            'CHECKED': 0.10,
            'APPROVED': 0.10,
            'SCALE': 0.10,
            'TITLE': 0.15,
            'JOB': 0.10,
            'NO': 0.05,
            'NUMBER': 0.05,
            'REVISION': 0.10,
            'REV': 0.05,
            'CLIENT': 0.10,
            'ARCHITECT': 0.10,
            'ENGINEER': 0.10,
            'CONTRACTOR': 0.10
        }
        
        # Add points for each keyword found
        for keyword, weight in keywords.items():
            if keyword in text_upper:
                score += weight
        
        # Bonus for ideal length range (title blocks are typically 200-2000 chars)
        text_length = len(text)
        if 200 <= text_length <= 500:
            score += 0.25
        elif 500 < text_length <= 1000:
            score += 0.20
        elif 1000 < text_length <= 2000:
            score += 0.15
        elif text_length > 2000:
            score += 0.05
        
        # Check for drawing number patterns (e.g., E5.00, A-101, M601)
        drawing_patterns = [
            r'[A-Z]{1,3}[-.]?\d{1,3}(?:\.\d{1,3})?[A-Z]?',  # E5.00, A-101, M601A
            r'SHEET\s*:?\s*[A-Z0-9]',                         # SHEET: A101
            r'DWG\.?\s*NO\.?\s*:?\s*[A-Z0-9]',              # DWG NO: E5
        ]
        
        for pattern in drawing_patterns:
            if re.search(pattern, text_upper):
                score += 0.15
                break
        
        # Penalty if text appears truncated
        if self._looks_truncated(text):
            score *= 0.7
        
        # Normalize score to 0-1 range
        return min(score, 1.0)

    def _looks_truncated(self, text: str) -> bool:
        """
        Detect if text appears to be truncated.
        Returns True if the text seems to be cut off mid-word or mid-sentence.
        """
        if not text or len(text) < 50:
            return False
        
        text = text.rstrip()
        
        # Clear truncation indicators
        if text.endswith(('-', '/', '\\', '...')):
            return True
        
        # Check if ends with ellipsis pattern
        if re.search(r'\.\s*\.\s*\.$', text):
            return True
        
        # Get the last word
        words = text.split()
        if not words:
            return False
        
        last_word = words[-1].rstrip('.,;:!?')
        
        # Common short words that are valid endings (not truncated)
        valid_short_endings = {
            # Articles, prepositions, conjunctions
            'a', 'an', 'as', 'at', 'by', 'do', 'go', 'he', 'if', 'in', 'is', 'it', 
            'me', 'my', 'no', 'of', 'on', 'or', 'so', 'to', 'up', 'us', 'we',
            'for', 'the', 'and', 'but', 'nor', 'yet', 'all', 'any', 'are', 'can',
            'had', 'has', 'her', 'him', 'his', 'its', 'may', 'not', 'one', 'our',
            'out', 'she', 'too', 'two', 'was', 'who', 'why', 'you',
            # Common abbreviations
            'inc', 'llc', 'ltd', 'co', 'corp', 'st', 'rd', 'ave', 'dr', 'ct', 'ln',
            'blvd', 'pkwy', 'hwy', 'ft', 'sq', 'mi', 'km', 'mm', 'cm', 'm',
            # Common drawing terms
            'no', 'yes', 'ok', 'na', 'tbd', 'typ', 'min', 'max', 'ref', 'rev',
            'dwg', 'sht', 'det', 'elev', 'sect', 'plan', 'schd', 'diag',
            # Months
            'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'
        }
        
        # Check if it's a valid short word
        if last_word.lower() in valid_short_endings:
            return False
        
        # Check for incomplete words (all caps, 1-4 letters)
        if len(last_word) <= 4 and last_word.isalpha() and last_word.isupper():
            # But exclude common abbreviations that are all caps
            common_caps = {'USA', 'LLC', 'INC', 'ASAP', 'HVAC', 'MEP', 'ADA', 'NEC', 'IBC'}
            if last_word not in common_caps:
                return True
        
        # Check for incomplete alphanumeric codes (like "E5-0" instead of "E5-01")
        if re.match(r'^[A-Z]{1,3}\d{0,2}[-.]?$', last_word):
            return True
        
        # Check if the text ends mid-sentence (no proper punctuation)
        last_char = text[-1]
        if last_char.isalnum() and len(text) < 300:
            # Short text ending with alphanumeric might be truncated
            # But only if it's not ending with a common abbreviation
            if not any(text.upper().endswith(abbr.upper()) for abbr in valid_short_endings):
                return True
        
        return False

    def _extract_project_name_from_titleblock(self, titleblock_text: str) -> Tuple[Optional[str], str, bool]:
        """
        Extract project name from title block text with source tracking.
        Returns: (project_name, source, is_truncated)
        """
        if not titleblock_text:
            return None, "not_found", False
        
        project_name = None
        source = "not_found"
        
        # Try to find labeled project name
        patterns = [
            (r'PROJECT\s*(?:NAME)?\s*:?\s*([^\n\r]+)', "project_label"),
            (r'TITLE\s*:?\s*([^\n\r]+)', "title_label"),
            (r'JOB\s*(?:NAME)?\s*:?\s*([^\n\r]+)', "job_label"),
            (r'(?:^|\n)([A-Z][A-Z\s\-&]+(?:PROJECT|BUILDING|CENTER|FACILITY|COMPLEX|TOWER|PLAZA))', "inferred"),
        ]
        
        for pattern, pattern_source in patterns:
            match = re.search(pattern, titleblock_text, re.IGNORECASE | re.MULTILINE)
            if match:
                candidate = match.group(1).strip(": -\t")
                # Clean up the project name
                candidate = re.sub(r'\s+', ' ', candidate)  # Normalize whitespace
                candidate = candidate.strip()
                
                if candidate and len(candidate) > 3:
                    project_name = candidate
                    source = pattern_source
                    break
        
        # Check if the found project name appears truncated
        is_truncated = False
        if project_name:
            last_word = project_name.split()[-1] if project_name.split() else ""
            if last_word and len(last_word) <= 4 and last_word.isalpha() and last_word.isupper():
                # Check if it's not a valid abbreviation
                valid_abbrevs = {'LLC', 'INC', 'CORP', 'LTD', 'ASSN', 'INTL', 'NATL', 'BLDG'}
                if last_word not in valid_abbrevs:
                    is_truncated = True
        
        return project_name, source, is_truncated

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
                titleblock_text = self._extract_titleblock_region_text(doc, page_num=0)
                if titleblock_text:
                    self.logger.info(f"Extracted {len(titleblock_text)} chars from title block")

            # Process each page individually to avoid reference issues
            enable_table_extraction = os.getenv("ENABLE_TABLE_EXTRACTION", "true").lower() == "true"
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
                if enable_table_extraction:
                    try:
                        # Only attempt table extraction if page has text
                        page_text = page.get_text("text")
                        if page_text and page_text.strip():
                            try:
                                table_finder = page.find_tables()
                                if table_finder and hasattr(table_finder, "tables"):
                                    for j, table in enumerate(table_finder.tables or []):
                                        try:
                                            if hasattr(table, 'to_markdown'):
                                                table_markdown = table.to_markdown()
                                                if table_markdown:
                                                    tables.append({
                                                        "page": i + 1,
                                                        "table_index": j,
                                                        "content": table_markdown,
                                                    })
                                        except Exception as e:
                                            # Skip individual table errors
                                            self.logger.debug(f"Skipping table {j} on page {i+1}: {str(e)}")
                            except AttributeError:
                                # Page doesn't support tables - this is normal
                                self.logger.debug(f"Page {i+1} doesn't support table extraction")
                    except Exception as e:
                        # Log at debug level since this isn't critical
                        self.logger.debug(f"Table extraction skipped for page {i+1}: {str(e)}")
                else:
                    if not table_notice_logged:
                        self.logger.info("ENABLE_TABLE_EXTRACTION=false; skipping PyMuPDF table detection for speed")
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
                drawing_type=detected_drawing_type
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
                None, self._save_page_as_image, file_path, page_num, output_path, dpi
            )

            return result
        except Exception as e:
            self.logger.error(f"Error saving page as image: {str(e)}")
            raise

    def _save_page_as_image(
        self, file_path: str, page_num: int, output_path: str, dpi: int = 300
    ) -> str:
        """
        Internal method to save a PDF page as an image.
        This method runs in a separate thread.

        Args:
            file_path: Path to the PDF file
            page_num: Page number to extract (0-based)
            output_path: Path to save the image
            dpi: DPI for the rendered image

        Returns:
            Path to the saved image
        """
        with fitz.open(file_path) as doc:
            if page_num < 0 or page_num >= len(doc):
                raise IndexError(
                    f"Page number {page_num} out of range (0-{len(doc)-1})"
                )

            page = doc[page_num]
            pixmap = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
            pixmap.save(output_path)

            self.logger.info(f"Saved page {page_num} as image: {output_path}")
            return output_path


class ArchitecturalExtractor(PyMuPdfExtractor):
    """Specialized extractor for architectural drawings."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)

    async def extract(self, file_path: str) -> ExtractionResult:
        """Extract architectural-specific content from PDF."""
        # Get base extraction using parent method
        result = await super().extract(file_path)

        if not result.success:
            return result

        # Check for content before attempting enhancements
        if not result.has_content:
            self.logger.info(
                f"Skipping architectural enhancement for {file_path}: No base content found."
            )
            return result

        # Enhance extraction with architectural-specific processing
        try:
            # Extract room information more effectively
            enhanced_text = self._enhance_room_information(result.raw_text)
            result.raw_text = enhanced_text

            # Prioritize tables containing room schedules, door schedules, etc.
            prioritized_tables = self._prioritize_architectural_tables(result.tables)
            result.tables = prioritized_tables

            self.logger.info(f"Enhanced architectural extraction for {file_path}")
            return result
        except Exception as e:
            self.logger.warning(
                f"Error in architectural enhancement for {file_path}: {str(e)}"
            )
            # Fall back to base extraction on error
            return result

    def _enhance_room_information(self, text: str) -> str:
        """Extract and highlight room information in text."""
        # Add a marker for room information
        if "room" in text.lower() or "space" in text.lower():
            text = "ROOM INFORMATION DETECTED:\n" + text
        return text

    def _prioritize_architectural_tables(
        self, tables: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Prioritize architectural tables by type."""
        # Prioritize tables likely to be room schedules
        room_tables = []
        other_tables = []

        for table in tables:
            content = table.get("content", "").lower()
            if "room" in content or "space" in content or "finish" in content:
                room_tables.append(table)
            else:
                other_tables.append(table)

        return room_tables + other_tables


class ElectricalExtractor(PyMuPdfExtractor):
    """Specialized extractor for electrical drawings."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)

    def _detect_subtype(self, file_path: str) -> str:
        """
        Detect electrical drawing subtype from filename.

        Args:
            file_path: Path to the file being analyzed

        Returns:
            String representing the detected subtype
        """
        filename = os.path.basename(file_path).lower()

        if "spec" in filename or "specification" in filename:
            return "specification"
        elif "panel" in filename or "schedule" in filename:
            return "panel_schedule"
        elif "lighting" in filename:
            return "lighting"
        elif "power" in filename or "riser" in filename:
            return "power"
        else:
            return "general"

    async def extract(self, file_path: str) -> ExtractionResult:
        """Extract electrical-specific content from PDF."""
        # Get base extraction using parent method
        result = await super().extract(file_path)

        if not result.success:
            return result

        # Check for content before attempting enhancements
        if not result.has_content:
            self.logger.info(
                f"Skipping electrical enhancement for {file_path}: No base content found."
            )
            return result
            
        # SKIP ENHANCEMENT FOR SPECIFICATION DOCUMENTS
        if "spec" in os.path.basename(file_path).lower():
            self.logger.info(f"Skipping panel enhancement for specification document {file_path}")
            # Just add a simple marker that doesn't trigger panel schedule detection
            result.raw_text = "SPECIFICATION DOCUMENT:\n" + result.raw_text
            return result

        # Enhance extraction with electrical-specific processing
        try:
            # Focus on panel schedules and circuit information
            enhanced_text = self._enhance_panel_information(result.raw_text)
            result.raw_text = enhanced_text

            # Prioritize tables containing panel schedules
            prioritized_tables = self._prioritize_electrical_tables(result.tables)
            result.tables = prioritized_tables

            # Add metadata to indicate panel schedule presence
            self._add_panel_metadata(result, file_path)

            self.logger.info(f"Enhanced electrical extraction for {file_path}")
            return result
        except Exception as e:
            self.logger.warning(
                f"Error in electrical enhancement for {file_path}: {str(e)}"
            )
            # Fall back to base extraction on error
            return result

    def _enhance_panel_information(self, text: str) -> str:
        """Extract and highlight panel information in text."""
        # Add a marker for panel information
        if "panel" in text.lower() or "circuit" in text.lower():
            text = "PANEL INFORMATION DETECTED:\n" + text

        # Specifically enhance panel schedule structure
        if self._is_panel_schedule(text):
            # Add clear section markers
            text = (
                "===PANEL SCHEDULE BEGINS===\n" + text + "\n===PANEL SCHEDULE ENDS==="
            )

            # Add structural hints for AI processing
            text = self._add_panel_structure_hints(text)

        return text

    def _is_panel_schedule(self, text: str) -> bool:
        """Determine if text contains a panel schedule."""
        # Look for key indicators of panel schedules
        panel_indicators = [
            "CKT" in text,
            "BREAKER" in text and "PANEL" in text,
            "CIRCUIT" in text and "LOAD" in text,
            "PANEL" in text and "SCHEDULE" in text,
            "POLES" in text and "TRIP" in text and "A" in text,
            # Common pattern of circuit numbers
            bool(re.search(r"\b\d+\s*[,-]\s*\d+\b", text)),
        ]

        # If at least two indicators are present, it's likely a panel schedule
        return sum(panel_indicators) >= 2

    def _add_panel_structure_hints(self, text: str) -> str:
        """Add structural hints to panel schedule text for AI processing."""
        # Add a hint about the left-right circuit arrangement
        hint = """
HINT: THIS IS A PANEL SCHEDULE WITH TABULAR STRUCTURE.
- Left side (odd numbered) circuits and right side (even numbered) circuits are typically paired
- CKT or Circuit columns indicate circuit numbers
- A/B/C columns indicate phase loads
- Load Classification shows the type of each circuit
- Trip/Poles shows the breaker configuration

IMPORTANT FOR JSON STRUCTURE:
- Group all circuits by panel name
- Preserve circuit numbers for all entries
- Maintain the left/right pairing arrangement
- Include all phase loading data (A, B, C) when present
"""
        return hint + "\n\n" + text

    def _add_panel_metadata(self, result: ExtractionResult, file_path: str) -> None:
        """Add panel schedule metadata to the extraction result."""
        # Initialize metadata if not present
        if result.metadata is None:
            result.metadata = {}

        # Check if filename or content suggests panel schedule
        filename = os.path.basename(file_path).lower()

        result.metadata["contains_panel_schedule"] = (
            "panel" in filename and "schedule" in filename
        ) or self._is_panel_schedule(result.raw_text)

        # Add panel names if detected
        panel_names = self._extract_panel_names(result.raw_text)
        if panel_names:
            result.metadata["panel_names"] = panel_names

    def _extract_panel_names(self, text: str) -> List[str]:
        """Extract panel names from text."""
        panel_names = []

        # Look for common panel name patterns
        panel_patterns = [
            r"Panel:?\s*([A-Za-z0-9\-\.]+)",
            r"PANEL\s*([A-Za-z0-9\-\.]+)",
            r"([A-Za-z0-9\-\.]+)\s*PANEL SCHEDULE",
        ]

        for pattern in panel_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            panel_names.extend(matches)

        # Remove duplicates while preserving order
        seen = set()
        unique_names = []
        for name in panel_names:
            if name.upper() not in seen:
                seen.add(name.upper())
                unique_names.append(name)

        return unique_names

    def _prioritize_electrical_tables(
        self, tables: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Prioritize electrical tables - panel schedules first."""
        # Move panel schedules to the top
        panel_tables = []
        other_tables = []

        for table in tables:
            content = table.get("content", "").lower()
            is_panel_schedule = (
                ("panel" in content and "circuit" in content)
                or ("ckt" in content and "trip" in content)
                or ("breaker" in content and "poles" in content)
            )

            if is_panel_schedule:
                # Add a hint for the AI processor
                if "content" in table:
                    table["content"] = "PANEL SCHEDULE TABLE:\n" + table["content"]
                panel_tables.append(table)
            else:
                other_tables.append(table)

        return panel_tables + other_tables


class MechanicalExtractor(PyMuPdfExtractor):
    """Specialized extractor for mechanical drawings."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)

    async def extract(self, file_path: str) -> ExtractionResult:
        """Extract mechanical-specific content from PDF."""
        # Use parent extraction method
        result = await super().extract(file_path)

        if not result.success:
            return result

        # Check for content before attempting enhancements
        if not result.has_content:
            self.logger.info(
                f"Skipping mechanical enhancement for {file_path}: No base content found."
            )
            return result

        # Enhance extraction with mechanical-specific processing
        try:
            # Focus on equipment schedules
            enhanced_text = self._enhance_equipment_information(result.raw_text)
            result.raw_text = enhanced_text

            # Prioritize tables containing equipment schedules
            prioritized_tables = self._prioritize_mechanical_tables(result.tables)
            result.tables = prioritized_tables

            self.logger.info(f"Enhanced mechanical extraction for {file_path}")
            return result
        except Exception as e:
            self.logger.warning(
                f"Error in mechanical enhancement for {file_path}: {str(e)}"
            )
            # Fall back to base extraction on error
            return result

    def _enhance_equipment_information(self, text: str) -> str:
        """Extract and highlight equipment information in text."""
        # Add a marker for equipment information
        if (
            "equipment" in text.lower()
            or "hvac" in text.lower()
            or "cfm" in text.lower()
        ):
            text = "EQUIPMENT INFORMATION DETECTED:\n" + text
        return text

    def _prioritize_mechanical_tables(
        self, tables: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Prioritize mechanical tables - equipment schedules first."""
        # Simple heuristic - look for equipment-related terms
        equipment_tables = []
        other_tables = []

        for table in tables:
            content = table.get("content", "").lower()
            if any(term in content for term in ["equipment", "hvac", "cfm", "tonnage"]):
                equipment_tables.append(table)
            else:
                other_tables.append(table)

        return equipment_tables + other_tables


class PlumbingExtractor(PyMuPdfExtractor):
    """Specialized extractor for plumbing drawings."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)

    async def extract(self, file_path: str) -> ExtractionResult:
        # Base extraction using parent method
        result = await super().extract(file_path)

        if not result.success:
            return result

        # Check for content before attempting enhancements
        if not result.has_content:
            self.logger.info(
                f"Skipping plumbing enhancement for {file_path}: No base content found."
            )
            return result

        # Enhance extraction with plumbing-specific processing
        try:
            # Add simple type marker - this is where most performance gains come from
            enhanced_text = self._enhance_plumbing_information(result.raw_text)
            result.raw_text = enhanced_text

            # Prioritize tables containing fixture schedules, pipe schedules, etc.
            prioritized_tables = self._prioritize_plumbing_tables(result.tables)
            result.tables = prioritized_tables

            self.logger.info(f"Enhanced plumbing extraction for {file_path}")
            return result
        except Exception as e:
            self.logger.warning(
                f"Error in plumbing enhancement for {file_path}: {str(e)}"
            )
            # Fall back to base extraction on error
            return result

    def _enhance_plumbing_information(self, text: str) -> str:
        """Extract and highlight plumbing information in text."""
        # Add a marker for plumbing information - keep it simple
        enhanced_text = "PLUMBING CONTENT:\n" + text

        # Only mark the most important sections - fixtures, water heaters, etc.
        if any(
            term in text.lower()
            for term in ["fixture", "water closet", "lavatory", "sink"]
        ):
            enhanced_text = "FIXTURE INFORMATION DETECTED:\n" + enhanced_text

        if any(
            term in text.lower()
            for term in ["water heater", "hot water", "domestic water"]
        ):
            enhanced_text = "WATER HEATER INFORMATION DETECTED:\n" + enhanced_text

        if any(term in text.lower() for term in ["pipe", "piping", "valve"]):
            enhanced_text = "PIPING INFORMATION DETECTED:\n" + enhanced_text

        return enhanced_text

    def _prioritize_plumbing_tables(
        self, tables: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Prioritize plumbing tables - fixture schedules first."""
        # Focus on just a few critical keywords for scoring tables
        fixture_tables = []
        equipment_tables = []
        pipe_tables = []
        other_tables = []

        for table in tables:
            content = table.get("content", "").lower()

            # Check for just the most important keywords
            if any(
                term in content for term in ["fixture", "wc", "lav", "sink", "urinal"]
            ):
                fixture_tables.append(table)
            elif any(
                term in content
                for term in ["water heater", "pump", "water temperature"]
            ):
                equipment_tables.append(table)
            elif any(term in content for term in ["pipe", "valve", "fitting"]):
                pipe_tables.append(table)
            else:
                other_tables.append(table)

        # Return prioritized tables - most important first
        return fixture_tables + equipment_tables + pipe_tables + other_tables


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
