"""
Mechanical drawing extractor.
"""
import logging
from typing import List, Dict, Any, Optional

from .base import PyMuPdfExtractor
from .models import ExtractionResult


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

