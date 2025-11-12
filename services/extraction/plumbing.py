"""
Plumbing drawing extractor.
"""
import logging
from typing import List, Dict, Any, Optional

from .base import PyMuPdfExtractor
from .models import ExtractionResult


class PlumbingExtractor(PyMuPdfExtractor):
    """Specialized extractor for plumbing drawings."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)

    async def extract(self, file_path: str) -> ExtractionResult:
        """Extract plumbing-specific content from PDF."""
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

