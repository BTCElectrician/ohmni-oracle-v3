"""
Lightweight text-based heuristics for electrical panel schedule extraction.

This module provides neutral, regex-based heuristics that work with raw PDF text
to detect panels, classify circuit rows, and provide structure hints for AI processing.
Designed to be minimal and avoid over-engineering while still helping the AI
understand panel schedule structure.
"""
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter


AMP_RE = re.compile(r"(\d+)\s*A\b", re.I)
LOAD_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(VA|KVA|KW)\b", re.I)
PANEL_HEADER_RE = re.compile(r"^panel\s*:?\s*([A-Z0-9\-\.]+)", re.I)
SUMMARY_KEYWORDS = {"total", "connected", "demand factor", "panel totals", "%"}
CIRCUIT_HEADER_KEYWORDS = {
    "ckt": ["ckt", "circuit", "cir."],
    "load": ["load", "desc", "description", "name"],
    "breaker": ["trip", "breaker", "amps", "a"],
    "poles": ["poles", "pole", "p"],
    "phase": ["phase", "ph", "a", "b", "c"],
}


def split_into_panels(lines: List[str]) -> List[Dict[str, Any]]:
    """
    Split text lines into panel blocks by detecting panel headers.
    
    Args:
        lines: List of text lines from PDF extraction
        
    Returns:
        List of panel dictionaries with keys: panel_id, start, end, lines
    """
    panels = []
    current = None
    
    for idx, line in enumerate(lines):
        match = PANEL_HEADER_RE.match(line.strip())
        if match:
            if current:
                current["end"] = idx
                panels.append(current)
            
            panel_id = match.group(1).upper()
            if len(panel_id) >= 1:
                current = {
                    "panel_id": panel_id,
                    "start": idx,
                    "lines": [],
                }
        
        if current:
            current["lines"].append(line)
    
    if current:
        current["end"] = len(lines)
        panels.append(current)
    
    return panels


def strip_titleblock_noise(panel_lines: List[str]) -> List[str]:
    """
    Filter out legend/title block noise from panel lines.
    
    Keeps lines between Panel: header and first obvious summary line.
    
    Args:
        panel_lines: Lines belonging to a panel block
        
    Returns:
        Filtered list of lines with noise removed
    """
    if not panel_lines:
        return []
    
    filtered = []
    in_panel_content = False
    found_summary = False
    
    for line in panel_lines:
        line_lower = line.lower()
        
        if PANEL_HEADER_RE.search(line):
            in_panel_content = True
            filtered.append(line)
            continue
        
        if not in_panel_content:
            continue
        
        if is_summary_line(line):
            found_summary = True
            break
        
        filtered.append(line)
    
    return filtered


def classify_line(line: str) -> str:
    """
    Classify a line as circuit, summary, or other.
    
    Args:
        line: Text line to classify
        
    Returns:
        One of: "circuit", "summary", "other"
    """
    line_lower = line.lower()
    
    if is_summary_line(line):
        return "summary"
    
    if is_circuit_row(line):
        return "circuit"
    
    return "other"


def is_circuit_row(line: str) -> bool:
    """
    Determine if a line represents a circuit row.
    
    A circuit row must have:
    - At least one breaker rating (amps)
    - At least one load value (VA/KVA/KW) OR descriptive text with amps
    - Not contain summary keywords
    
    Args:
        line: Text line to check
        
    Returns:
        True if line appears to be a circuit row
    """
    line_lower = line.lower()
    
    if any(keyword in line_lower for keyword in SUMMARY_KEYWORDS):
        return False
    
    has_amps = bool(AMP_RE.search(line))
    has_load = bool(LOAD_RE.search(line))
    
    if has_amps and has_load:
        return True
    
    if has_amps and len(line.strip()) >= 12:
        return True
    
    return False


def is_summary_line(line: str) -> bool:
    """
    Determine if a line represents a summary/totals line.
    
    Args:
        line: Text line to check
        
    Returns:
        True if line appears to be a summary line
    """
    line_lower = line.lower()
    
    has_summary_keyword = any(keyword in line_lower for keyword in SUMMARY_KEYWORDS)
    has_load_or_amp = bool(LOAD_RE.search(line) or AMP_RE.search(line))
    
    return has_summary_keyword and has_load_or_amp


def detect_circuits_per_line(panel_lines: List[str]) -> int:
    """
    Detect whether panel uses 1 or 2 circuits per line.
    
    Samples first 10 candidate circuit lines and counts breaker ratings.
    Typical line with 2 matches → two circuits per line.
    Typical line with 1 match → one circuit per line.
    
    Args:
        panel_lines: Lines from a panel block
        
    Returns:
        1 or 2 indicating circuits per line
    """
    circuit_lines = []
    for line in panel_lines:
        if is_circuit_row(line):
            circuit_lines.append(line)
            if len(circuit_lines) >= 10:
                break
    
    if not circuit_lines:
        return 1
    
    amp_counts = []
    for line in circuit_lines:
        matches = list(AMP_RE.finditer(line))
        amp_counts.append(len(matches))
    
    if not amp_counts:
        return 1
    
    counter = Counter(amp_counts)
    most_common_count, most_common_freq = counter.most_common(1)[0]
    
    return 2 if most_common_count >= 2 else 1


def find_header_row(panel_lines: List[str]) -> Optional[int]:
    """
    Find the header row index within panel lines.
    
    Looks for a line containing circuit, load, and breaker keywords.
    
    Args:
        panel_lines: Lines from a panel block
        
    Returns:
        Index of header row, or None if not found
    """
    for idx, line in enumerate(panel_lines):
        line_lower = line.lower()
        
        has_ckt = any(kw in line_lower for kw in CIRCUIT_HEADER_KEYWORDS["ckt"])
        has_load = any(kw in line_lower for kw in CIRCUIT_HEADER_KEYWORDS["load"])
        has_breaker = any(kw in line_lower for kw in CIRCUIT_HEADER_KEYWORDS["breaker"])
        
        if has_ckt and has_load and has_breaker:
            return idx
    
    return None


def extract_panel_metadata(panel_lines: List[str]) -> Dict[str, Any]:
    """
    Extract panel metadata from header area using generic Label: Value patterns.
    
    Args:
        panel_lines: Lines from a panel block (first ~10 lines typically contain metadata)
        
    Returns:
        Dictionary with extracted metadata fields
    """
    metadata = {}
    header_text = "\n".join(panel_lines[:10])
    
    rating_match = re.search(r"rating\s*:\s*(\d+)\s*A", header_text, re.I)
    if rating_match:
        metadata["rating_amps"] = int(rating_match.group(1))
    
    voltage_match = re.search(r"volts?\s*:\s*([0-9/\s]+(?:wye|delta)?)", header_text, re.I)
    if voltage_match:
        metadata["voltage"] = voltage_match.group(1).strip()
    
    type_match = re.search(r"type\s*:\s*([A-Z]+)", header_text, re.I)
    if type_match:
        metadata["type"] = type_match.group(1)
    
    supply_match = re.search(r"supply\s+from\s*:\s*([A-Z0-9\-]+)", header_text, re.I)
    if supply_match:
        metadata["supply_from"] = supply_match.group(1)
    
    aic_match = re.search(r"a\.?i\.?c\.?\s*rating\s*:\s*([0-9K]+)", header_text, re.I)
    if aic_match:
        metadata["aic_rating"] = aic_match.group(1)
    
    return metadata


def annotate_text_with_panel_markers(
    raw_text: str, panels: List[Dict[str, Any]]
) -> str:
    """
    Annotate raw text with panel schedule markers for AI structure hints.
    
    Adds markers like "=== PANEL SCHEDULE: K1 ===" around each panel block.
    
    Args:
        raw_text: Original extracted text
        panels: List of panel dictionaries from split_into_panels
        
    Returns:
        Annotated text with panel markers
    """
    if not panels:
        return raw_text
    
    lines = raw_text.split("\n")
    annotated_lines = []
    panel_idx = 0
    
    for line_idx, line in enumerate(lines):
        if panel_idx < len(panels):
            panel = panels[panel_idx]
            
            if line_idx == panel["start"]:
                if panel_idx > 0:
                    prev_panel = panels[panel_idx - 1]
                    annotated_lines.append(f"=== END PANEL SCHEDULE: {prev_panel['panel_id']} ===")
                
                marker = f"=== PANEL SCHEDULE: {panel['panel_id']} ==="
                annotated_lines.append(marker)
                annotated_lines.append(line)
            elif line_idx == panel["end"] - 1:
                annotated_lines.append(line)
                if panel_idx == len(panels) - 1:
                    annotated_lines.append(f"=== END PANEL SCHEDULE: {panel['panel_id']} ===")
                panel_idx += 1
            else:
                annotated_lines.append(line)
        else:
            annotated_lines.append(line)
    
    return "\n".join(annotated_lines)


def score_table_for_panel(table: Dict[str, Any], panel_id: str) -> float:
    """
    Score a table's relevance to a panel schedule.
    
    Higher scores indicate tables more likely to be panel-related.
    
    Args:
        table: Table dictionary from extraction
        panel_id: Panel identifier to match against
        
    Returns:
        Score (higher = more relevant)
    """
    score = 0.0
    
    table_text = str(table.get("data", "")).lower()
    table_text += " " + str(table.get("headers", "")).lower()
    
    if panel_id.lower() in table_text:
        score += 10.0
    
    if any(kw in table_text for kw in ["circuit", "ckt", "breaker", "trip"]):
        score += 5.0
    
    if any(kw in table_text for kw in ["load", "va", "amps"]):
        score += 3.0
    
    if "panel" in table_text:
        score += 2.0
    
    return score


def process_panel_text(raw_text: str, logger: Optional[logging.Logger] = None) -> Dict[str, Any]:
    """
    Main entry point: process raw text and return structured panel information.
    
    Args:
        raw_text: Raw extracted text from PDF
        logger: Optional logger for observability
        
    Returns:
        Dictionary with keys:
        - annotated_text: Text with panel markers
        - panels: List of panel dictionaries with metadata
        - panel_count: Number of panels detected
    """
    if not raw_text or not raw_text.strip():
        return {
            "annotated_text": raw_text,
            "panels": [],
            "panel_count": 0,
        }
    
    lines = raw_text.split("\n")
    panels = split_into_panels(lines)
    
    if not panels:
        if logger:
            logger.debug("No panels detected in text")
        return {
            "annotated_text": raw_text,
            "panels": [],
            "panel_count": 0,
        }
    
    processed_panels = []
    for panel in panels:
        panel_lines = panel["lines"]
        filtered_lines = strip_titleblock_noise(panel_lines)
        
        circuits_per_line = detect_circuits_per_line(filtered_lines)
        header_row_idx = find_header_row(filtered_lines)
        metadata = extract_panel_metadata(filtered_lines)
        
        circuit_count = sum(1 for line in filtered_lines if is_circuit_row(line))
        
        processed_panel = {
            "panel_id": panel["panel_id"],
            "start_line": panel["start"],
            "end_line": panel["end"],
            "circuits_per_line": circuits_per_line,
            "header_row_idx": header_row_idx,
            "circuit_count": circuit_count,
            "metadata": metadata,
        }
        processed_panels.append(processed_panel)
        
        if logger:
            logger.info(
                f"Detected panel {panel['panel_id']}: "
                f"{circuit_count} circuits, {circuits_per_line} per line"
            )
    
    annotated_text = annotate_text_with_panel_markers(raw_text, panels)
    
    return {
        "annotated_text": annotated_text,
        "panels": processed_panels,
        "panel_count": len(panels),
    }

