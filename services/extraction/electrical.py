"""
Electrical drawing extractor with panel schedule support.
"""
import os
import re
import logging
from typing import List, Dict, Any, Optional

import pymupdf as fitz

from utils.minimal_panel_clip import (
    panel_rects,
    get_panel_text_blocks,
)

from .base import PyMuPdfExtractor
from .models import ExtractionResult


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
            self.logger.info(
                f"Skipping panel enhancement for specification document {file_path}"
            )
            # Just add a simple marker that doesn't trigger panel schedule detection
            result.raw_text = "SPECIFICATION DOCUMENT:\n" + result.raw_text
            return result

        # Enhance extraction with electrical-specific processing
        try:
            # Check if this is a panel schedule
            if self._is_panel_schedule(result.raw_text):
                # Use per-panel extraction
                enhanced_text = await self._extract_panels_separately(file_path)
                result.raw_text = enhanced_text
            else:
                # Use standard enhancement for non-panel drawings
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

    async def _extract_panels_separately(self, file_path: str) -> str:
        """Extract panels separately using clipping to prevent cross-panel bleeding."""
        try:
            doc = fitz.open(file_path)
            all_panels_text = []

            # Process each page
            for page_num, page in enumerate(doc):
                # Get panel rectangles for this page
                panels = panel_rects(page)

                if panels:
                    self.logger.info(f"Found {len(panels)} panels on page {page_num + 1}")

                    # Extract each panel separately
                    for panel_name, rect in panels:
                        # Extract text from this panel's rectangle
                        panel_text = get_panel_text_blocks(page, rect)

                        # Add panel header and markers
                        panel_section = f"\n===PANEL {panel_name} BEGINS===\n"
                        panel_section += f"Panel: {panel_name}\n"
                        panel_section += panel_text
                        panel_section += f"\n===PANEL {panel_name} ENDS===\n"

                        all_panels_text.append(panel_section)

                        self.logger.debug(
                            f"Extracted panel {panel_name} with {len(panel_text)} chars"
                        )
                else:
                    # No panels detected on this page, extract normally
                    page_text = page.get_text("text", sort=True)
                    if page_text.strip():
                        all_panels_text.append(page_text)

            doc.close()

            # Combine all panel texts
            combined_text = "\n".join(all_panels_text)

            # Add structural hints for AI processing
            combined_text = self._add_panel_structure_hints(combined_text)

            return combined_text

        except Exception as e:
            self.logger.error(f"Error in per-panel extraction: {str(e)}")
            # Fall back to regular extraction
            raise

