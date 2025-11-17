"""
Electrical drawing extractor with panel schedule support.
"""
import os
import re
import logging
from typing import List, Dict, Any, Optional

import pymupdf as fitz

from utils.minimal_panel_clip import (
    segment_panels,
    get_panel_text_blocks,
    detect_column_headers,
    map_values_to_columns,
    normalize_left_right,
)
from config.settings import (
    PANEL_Y_TOL_MAX,
    PANEL_Y_TOL_FRAC,
    PANEL_PAD,
    PANEL_HEADER_TOL,
    PANEL_HEADER_TOL_RETRY,
    PANEL_MIN_ROWS_FOR_PANEL,
    PANEL_EXPECTED_MIN_CIRCUITS,
    PANEL_MAX_RETRY_ATTEMPTS,
    PANEL_DEBUG_MODE,
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
        """
        Extract panels separately using column-mapped extraction to prevent cross-panel bleeding.
        
        Uses segment_panels for accurate segmentation, splits each panel into left/right halves,
        maps values to columns, pairs odd/even circuits, and emits structured text.
        """
        try:
            doc = fitz.open(file_path)
            all_panels_text = []
            sheet_summaries = []

            # Compute adaptive y_tol
            page_rect = doc[0].rect if len(doc) > 0 else None
            y_tol = (
                min(PANEL_Y_TOL_MAX, page_rect.height * PANEL_Y_TOL_FRAC)
                if page_rect
                else PANEL_Y_TOL_MAX
            )

            # Process each page
            for page_num, page in enumerate(doc):
                # Segment panels with adaptive y_tol
                panels = segment_panels(page, y_tol=y_tol, pad=PANEL_PAD, logger=self.logger)

                # Log panel rects
                panel_info = [
                    f"({name},({rect.x0:.1f},{rect.y0:.1f},{rect.x1:.1f},{rect.y1:.1f}))"
                    for name, rect in panels
                ]
                self.logger.info(
                    f"page={page_num + 1} panels=[{','.join(panel_info)}]"
                )

                if panels:
                    self.logger.info(
                        f"Found {len(panels)} panels on page {page_num + 1}"
                    )

                    # Extract each panel separately
                    for panel_name, rect in panels:
                        # Filter out sheet summaries
                        SUMMARY_NAMES = {"TOTALS", "SUMMARY", "LOAD", "LOAD SUMMARY"}
                        if panel_name in SUMMARY_NAMES:
                            self.logger.debug(f"summary_block detected: {panel_name}")
                            block_text = get_panel_text_blocks(page, rect)
                            sheet_summaries.append(
                                f"SHEET_SUMMARY: {panel_name}\n{block_text}"
                            )
                            continue

                        # Extract panel with column mapping
                        panel_data = self._extract_panel_struct(
                            page, panel_name, rect, header_tol=PANEL_HEADER_TOL
                        )

                        if panel_data.get("summary"):
                            # This is a sheet summary, not a panel
                            sheet_summaries.append(
                                f"SHEET_SUMMARY: {panel_name}\n{panel_data.get('summary', {}).get('raw_text', '')}"
                            )
                            continue

                        # Validate circuit count
                        circuits = panel_data.get("circuits", [])
                        circuit_count = len([c for c in circuits if c.get("circuit_number") is not None])
                        
                        if circuit_count < PANEL_EXPECTED_MIN_CIRCUITS:
                            self.logger.warning(
                                f"panel={panel_name} low_circuit_count={circuit_count} < {PANEL_EXPECTED_MIN_CIRCUITS} "
                                f"expected_minimum. This may indicate incomplete extraction. "
                                f"rect_height={rect.height:.1f} words_in_rect={len(page.get_text('words', clip=rect))}"
                            )
                        
                        # Build structured text output
                        panel_section = self._build_panel_text_section(
                            panel_name, panel_data
                        )
                        all_panels_text.append(panel_section)

                        # Log extraction metrics
                        paired_count = sum(
                            1 for c in circuits if c.get("paired_circuit")
                        )
                        self.logger.info(
                            f"panel={panel_name} circuits_emitted={circuit_count} paired_even={paired_count} "
                            f"validation={'PASS' if circuit_count >= PANEL_EXPECTED_MIN_CIRCUITS else 'WARN'}"
                        )

                else:
                    # No panels detected on this page, extract normally
                    page_text = page.get_text("text", sort=True)
                    if page_text.strip():
                        all_panels_text.append(page_text)
                        self.logger.info(
                            f"page={page_num + 1} extraction_mode=page-fallback"
                        )

            doc.close()

            # Combine all panel texts
            combined_text = "\n".join(all_panels_text)

            # Append sheet summaries if any
            if sheet_summaries:
                combined_text += "\n\n" + "\n\n".join(sheet_summaries)

            # Add structural hints for AI processing
            combined_text = self._add_panel_structure_hints(combined_text)

            return combined_text

        except Exception as e:
            self.logger.error(f"Error in per-panel extraction: {str(e)}")
            # Fall back to regular extraction
            raise

    def _extract_panel_struct(
        self, page: fitz.Page, name: str, rect: fitz.Rect, *, header_tol: float, retry_attempt: int = 0
    ) -> Dict[str, Any]:
        """
        Extract structured panel data with column mapping and circuit pairing.
        
        Args:
            page: PyMuPDF page object
            name: Panel name
            rect: Panel bounding rectangle
            header_tol: Header detection tolerance
            retry_attempt: Current retry attempt number (0 = first attempt)
        
        Returns:
            Dictionary with panel_name, metadata, circuits, or summary
        """
        # Check if this is a sheet summary
        SUMMARY_NAMES = {"TOTALS", "SUMMARY", "LOAD", "LOAD SUMMARY"}
        if name in SUMMARY_NAMES:
            block_text = get_panel_text_blocks(page, rect)
            return {"summary": {"raw_text": block_text}}

        # Split panel into left/right halves
        mid_x = (rect.x0 + rect.x1) / 2.0
        left_rect = fitz.Rect(rect.x0, rect.y0, mid_x, rect.y1)
        right_rect = fitz.Rect(mid_x, rect.y0, rect.x1, rect.y1)

        # Extract left side
        left_headers = detect_column_headers(page, left_rect, header_band_px=150.0)
        left_words = page.get_text("words", clip=left_rect, sort=True)
        left_mapped = map_values_to_columns(left_words, left_headers, tolerance=header_tol)

        # Extract right side
        right_headers = detect_column_headers(page, right_rect, header_band_px=150.0)
        right_words = page.get_text("words", clip=right_rect, sort=True)
        right_mapped = map_values_to_columns(
            right_words, right_headers, tolerance=header_tol
        )

        # Get block text for fallback
        block_text = get_panel_text_blocks(page, rect)

        # Log extraction metrics
        total_words = len(left_words) + len(right_words)
        total_mapped = len(left_mapped) + len(right_mapped)
        header_names = list(set(list(left_headers.keys()) + list(right_headers.keys())))
        self.logger.info(
            f"panel={name} attempt={retry_attempt} rect=[{rect.x0:.1f},{rect.y0:.1f},{rect.x1:.1f},{rect.y1:.1f}] "
            f"words={total_words} headers={header_names} mapped_rows={total_mapped} header_tol={header_tol:.1f}"
        )

        # Build row objects from mapped data
        left_rows = self._build_rows_from_mapped(left_mapped, side="left")
        right_rows = self._build_rows_from_mapped(right_mapped, side="right")

        # Pair left (odd) with right (even) circuits
        circuits = self._pair_circuits(left_rows, right_rows)

        # Log pairing statistics for debugging
        left_only = sum(1 for c in circuits if c.get("circuit_number") and not c.get("paired_circuit"))
        paired = sum(1 for c in circuits if c.get("paired_circuit"))
        right_only = len(circuits) - left_only - paired
        self.logger.debug(
            f"panel={name} pairing_stats: left_only={left_only} paired={paired} right_only={right_only} "
            f"total_circuits={len(circuits)}"
        )

        # Convert to format expected by normalize_left_right
        circuits_normalized = []
        for circuit in circuits:
            normalized = {
                "circuit_number": circuit.get("circuit_number"),
                "load_name": circuit.get("load_name"),
                "trip": circuit.get("trip"),
                "poles": circuit.get("poles"),
                "phase_loads": circuit.get("phase_loads", {"A": None, "B": None, "C": None}),
                "right_side": circuit.get("paired_circuit", {}),
            }
            circuits_normalized.append(normalized)

        # Apply normalize_left_right
        circuits_normalized = normalize_left_right(circuits_normalized)

        # Convert back to our format
        circuits = []
        for c in circuits_normalized:
            circuit = {
                "circuit_number": c.get("circuit_number"),
                "load_name": c.get("load_name"),
                "trip": c.get("trip"),
                "poles": c.get("poles"),
                "phase_loads": c.get("phase_loads", {"A": None, "B": None, "C": None}),
            }
            right_side = c.get("right_side", {})
            if right_side and right_side.get("circuit_number"):
                circuit["paired_circuit"] = right_side
            circuits.append(circuit)

        # Progressive retry logic with increasingly relaxed parameters
        circuit_count = len([c for c in circuits if c.get("circuit_number") is not None])
        needs_retry = (
            circuit_count < PANEL_MIN_ROWS_FOR_PANEL
            and len(block_text) > 1000
            and retry_attempt < PANEL_MAX_RETRY_ATTEMPTS
        )

        if needs_retry:
            retry_attempt += 1
            # Progressively expand rectangle and relax tolerance
            expand_factor = 5 + (retry_attempt * 10)  # 5, 15, 25, etc.
            new_header_tol = PANEL_HEADER_TOL_RETRY + (retry_attempt * 10)  # 45, 55, 65, etc.
            
            # Expand rect more aggressively, especially downward
            page_rect = page.rect
            expanded_rect = fitz.Rect(
                max(0, rect.x0 - expand_factor),
                max(0, rect.y0 - expand_factor),
                min(page_rect.x1, rect.x1 + expand_factor),
                min(page_rect.y1, rect.y1 + expand_factor * 2),  # Expand more downward
            )
            
            self.logger.warning(
                f"panel={name} low_circuit_count={circuit_count} < {PANEL_MIN_ROWS_FOR_PANEL}, "
                f"retry={retry_attempt}/{PANEL_MAX_RETRY_ATTEMPTS} expanding_rect by {expand_factor}pt, "
                f"relaxing_tol to {new_header_tol:.1f}"
            )
            
            return self._extract_panel_struct(
                page, name, expanded_rect, header_tol=new_header_tol, retry_attempt=retry_attempt
            )

        # Extract metadata from header band
        metadata = self._extract_panel_metadata(page, rect, name)

        return {
            "panel_name": name,
            "metadata": metadata,
            "circuits": circuits,
            "raw_text": block_text,
        }

    def _build_rows_from_mapped(
        self, mapped_rows: Dict[int, Dict[str, str]], side: str
    ) -> List[Dict[str, Any]]:
        """Build row objects from mapped column data."""
        rows = []
        for row_idx in sorted(mapped_rows.keys()):
            row_data = mapped_rows[row_idx]
            # Skip rows that have no textual content at all
            if not any(value.strip() for value in row_data.values() if value):
                continue
            row = {
                "circuit_number": self._parse_circuit_number(row_data.get("CKT", "")),
                "load_name": row_data.get("LOAD_NAME", "").strip() or None,
                "trip": self._parse_trip(row_data.get("TRIP", "")),
                "poles": self._parse_poles(row_data.get("POLES", "")),
                "phase_loads": {
                    "A": self._parse_phase_load(row_data.get("PHASE_A", "")),
                    "B": self._parse_phase_load(row_data.get("PHASE_B", "")),
                    "C": self._parse_phase_load(row_data.get("PHASE_C", "")),
                },
            }
            rows.append(row)
        return rows

    def _parse_circuit_number(self, value: str) -> Optional[int]:
        """Parse circuit number from string."""
        if not value:
            return None
        # Extract first number found
        match = re.search(r"\d+", str(value))
        return int(match.group()) if match else None

    def _parse_trip(self, value: str) -> Optional[str]:
        """Parse trip/breaker rating."""
        if not value:
            return None
        # Extract value like "20 A" or "20A" or just "20"
        value = str(value).strip()
        match = re.search(r"(\d+(?:\.\d+)?)\s*(?:A|AMP|AMPS)?", value, re.IGNORECASE)
        if match:
            return f"{match.group(1)} A"
        return value if value else None

    def _parse_poles(self, value: str) -> Optional[int]:
        """Parse number of poles."""
        if not value:
            return None
        match = re.search(r"\d+", str(value))
        return int(match.group()) if match else None

    def _parse_phase_load(self, value: str) -> Optional[str]:
        """Parse phase load value."""
        if not value:
            return None
        value = str(value).strip()
        # Extract numeric value with units if present
        match = re.search(r"(\d+(?:\.\d+)?)\s*(?:VA|W)?", value, re.IGNORECASE)
        return match.group(1) if match else value if value else None

    def _pair_circuits(
        self, left_rows: List[Dict[str, Any]], right_rows: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Pair left (odd) circuits with right (even) circuits.

        CRITICAL FIX: Emit circuits from BOTH sides, not just left.
        If left side is missing but right exists, emit the right circuit as primary.
        This prevents losing even-numbered circuits when left side extraction fails.
        """
        circuits = []
        max_len = max(len(left_rows), len(right_rows))

        for i in range(max_len):
            left = left_rows[i] if i < len(left_rows) else {}
            right = right_rows[i] if i < len(right_rows) else {}

            left_ckt = left.get("circuit_number")
            right_ckt = right.get("circuit_number")

            # Case 1: Both left and right have circuit numbers - emit left with paired right
            if left_ckt is not None and right_ckt is not None:
                circuit = {
                    "circuit_number": left_ckt,
                    "load_name": left.get("load_name"),
                    "trip": left.get("trip"),
                    "poles": left.get("poles"),
                    "phase_loads": left.get("phase_loads", {"A": None, "B": None, "C": None}),
                    "paired_circuit": {
                        "circuit_number": right_ckt,
                        "load_name": right.get("load_name"),
                        "trip": right.get("trip"),
                        "poles": right.get("poles"),
                        "phase_loads": right.get("phase_loads", {"A": None, "B": None, "C": None}),
                    }
                }
                circuits.append(circuit)

            # Case 2: Only left has circuit number - emit left without pairing
            elif left_ckt is not None:
                circuit = {
                    "circuit_number": left_ckt,
                    "load_name": left.get("load_name"),
                    "trip": left.get("trip"),
                    "poles": left.get("poles"),
                    "phase_loads": left.get("phase_loads", {"A": None, "B": None, "C": None}),
                }
                circuits.append(circuit)

            # Case 3: Only right has circuit number - emit right as primary (CRITICAL FIX)
            # This was the missing logic causing 35% circuit loss!
            elif right_ckt is not None:
                circuit = {
                    "circuit_number": right_ckt,
                    "load_name": right.get("load_name"),
                    "trip": right.get("trip"),
                    "poles": right.get("poles"),
                    "phase_loads": right.get("phase_loads", {"A": None, "B": None, "C": None}),
                }
                circuits.append(circuit)

            # Case 4: Neither side has circuit number - skip this row entirely
            # (This is expected for blank rows or headers)

        return circuits

    def _extract_panel_metadata(
        self, page: fitz.Page, rect: fitz.Rect, panel_name: str
    ) -> Dict[str, Any]:
        """Extract panel metadata from header band (<250pt from anchor)."""
        header_band = fitz.Rect(rect.x0, rect.y0, rect.x1, min(rect.y1, rect.y0 + 250))
        words = page.get_text("words", clip=header_band, sort=True)
        text = " ".join([w[4] for w in words]).upper()

        metadata = {}
        # Extract common metadata fields
        wires_match = re.search(r"(\d+)\s*WIRE", text)
        if wires_match:
            metadata["wires"] = int(wires_match.group(1))

        phases_match = re.search(r"(\d+)\s*PHASE", text)
        if phases_match:
            metadata["phases"] = int(phases_match.group(1))

        volts_match = re.search(r"(\d+)\s*V(?:OLT)?", text)
        if volts_match:
            metadata["volts"] = int(volts_match.group(1))

        rating_match = re.search(r"RATING[:\s]+(\d+)\s*(?:A|AMP)", text)
        if rating_match:
            metadata["rating"] = f"{rating_match.group(1)} A"

        type_match = re.search(r"TYPE[:\s]+([A-Z0-9\-]+)", text)
        if type_match:
            metadata["type"] = type_match.group(1)

        aic_match = re.search(r"AIC[:\s]+(\d+)", text)
        if aic_match:
            metadata["aic"] = int(aic_match.group(1))

        supply_match = re.search(r"SUPPLY\s+FROM[:\s]+([A-Z0-9\-]+)", text)
        if supply_match:
            metadata["supply_from"] = supply_match.group(1)

        return metadata

    def _build_panel_text_section(
        self, panel_name: str, panel_data: Dict[str, Any]
    ) -> str:
        """Build structured text section for a panel."""
        circuits = panel_data.get("circuits", [])
        metadata = panel_data.get("metadata", {})
        raw_text = panel_data.get("raw_text", "")

        section = f"\n===PANEL {panel_name} BEGINS===\n"
        section += f"Panel: {panel_name}\n"

        # Add metadata if present
        if metadata:
            section += "METADATA:\n"
            for key, value in metadata.items():
                if value:
                    section += f"  {key}: {value}\n"

        # Add structured circuits
        section += "\nCIRCUITS:\n"
        for circuit in circuits:
            ckt_num = circuit.get("circuit_number")
            if ckt_num is None:
                continue

            section += f"  Circuit {ckt_num}:\n"
            if circuit.get("load_name"):
                section += f"    Load Name: {circuit['load_name']}\n"
            if circuit.get("trip"):
                section += f"    Trip: {circuit['trip']}\n"
            if circuit.get("poles"):
                section += f"    Poles: {circuit['poles']}\n"
            if circuit.get("phase_loads"):
                phases = circuit["phase_loads"]
                phase_strs = []
                for phase in ["A", "B", "C"]:
                    if phases.get(phase):
                        phase_strs.append(f"{phase}={phases[phase]}")
                if phase_strs:
                    section += f"    Phase Loads: {', '.join(phase_strs)}\n"

            # Add paired circuit if present
            paired = circuit.get("paired_circuit")
            if paired and paired.get("circuit_number"):
                section += f"    Paired Circuit: {paired['circuit_number']}\n"
                if paired.get("load_name"):
                    section += f"      Load Name: {paired['load_name']}\n"
                if paired.get("trip"):
                    section += f"      Trip: {paired['trip']}\n"

        # Append raw block text for QA
        section += f"\nRAW_TEXT:\n{raw_text}\n"
        section += f"===PANEL {panel_name} ENDS===\n"

        return section

