"""
Architectural drawing extractor.
"""
import logging
from typing import List, Dict, Any, Optional

from .base import PyMuPdfExtractor
from .models import ExtractionResult


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

