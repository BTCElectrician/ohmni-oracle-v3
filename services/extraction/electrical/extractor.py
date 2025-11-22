"""
Electrical drawing extractor with panel schedule support.
"""
import logging
from typing import Optional

from ..base import PyMuPdfExtractor
from ..models import ExtractionResult
from .simple_panel_heuristics import (
    process_panel_text,
    score_table_for_panel,
)


class ElectricalExtractor(PyMuPdfExtractor):
    """
    Electrical extractor with lightweight panel schedule heuristics.
    
    Uses minimal text-based heuristics to detect panels and provide structure
    hints for AI processing, without heavy per-panel segmentation.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)

    def _is_spec_only(self, raw_text: str) -> bool:
        """
        Heuristic to detect if text is spec-only (no panel schedules).
        
        Args:
            raw_text: Extracted text to check
            
        Returns:
            True if text appears to be spec-only
        """
        text_lower = raw_text.lower()
        
        has_panel_marker = "panel" in text_lower and (
            "schedule" in text_lower or ":" in text_lower
        )
        
        has_circuit_indicators = any(
            kw in text_lower for kw in ["circuit", "ckt", "breaker", "trip"]
        )
        
        return not (has_panel_marker and has_circuit_indicators)

    async def extract(self, file_path: str) -> ExtractionResult:
        """
        Extract content from electrical PDF with lightweight panel heuristics.

        After base extraction, applies minimal text-based heuristics to:
        - Detect panel blocks and add structure markers
        - Extract panel metadata
        - Reorder tables by panel relevance
        """
        result = await super().extract(file_path)

        if not result.success or not result.has_content:
            return result

        self.logger.info(f"Applying lightweight panel heuristics for {file_path}")

        if self._is_spec_only(result.raw_text):
            self.logger.debug("Text appears spec-only, skipping panel heuristics")
            return result

        panel_info = process_panel_text(result.raw_text, logger=self.logger)

        result.raw_text = panel_info["annotated_text"]

        if panel_info["panel_count"] > 0:
            panel_metadata = {
                "panel_count": panel_info["panel_count"],
                "panels": panel_info["panels"],
            }
            
            if result.metadata is None:
                result.metadata = {}
            
            result.metadata["panel_schedules"] = panel_metadata
            
            self.logger.info(
                f"Detected {panel_info['panel_count']} panel(s): "
                f"{', '.join(p['panel_id'] for p in panel_info['panels'])}"
            )

            if result.tables:
                panel_ids = [p["panel_id"] for p in panel_info["panels"]]
                
                scored_tables = []
                for table in result.tables:
                    max_score = 0.0
                    best_panel = None
                    
                    for panel_id in panel_ids:
                        score = score_table_for_panel(table, panel_id)
                        if score > max_score:
                            max_score = score
                            best_panel = panel_id
                    
                    scored_tables.append((max_score, best_panel, table))
                
                scored_tables.sort(key=lambda x: x[0], reverse=True)
                result.tables = [table for _, _, table in scored_tables]
                
                self.logger.debug(
                    f"Reordered {len(result.tables)} tables by panel relevance"
                )

        return result

