"""
Minimal panel clipping utility for electrical panel schedule extraction.
This module provides functionality to detect and clip individual panels
from PDF pages to prevent cross-panel text bleeding.
"""
from __future__ import annotations
import re
import logging
from collections import defaultdict
from typing import List, Tuple, Optional, Dict, Any
HEADER_PATTERNS = {
    "CKT": r"^(CKT|CIRCUIT)$",
    "LOAD_NAME": r"^(LOAD\s*NAME|DESCRIPTION)$",
    "TRIP": r"^(TRIP|BKR)$",
    "POLES": r"^(POLES?|P)$",
    "PHASE_A": r"^(A|PHASE\s*A)$",
    "PHASE_B": r"^(B|PHASE\s*B)$",
    "PHASE_C": r"^(C|PHASE\s*C)$",
}

import fitz  # PyMuPDF

PANEL_RE = re.compile(r"\bpanel\b\s*:?\s*([A-Z0-9\-]+)", re.I)
AMP_RE = re.compile(r"\b\d+\s*A\b", re.I)
VA_RE = re.compile(r"\b\d[\d,]*\s*(?:VA|KVA|KW)\b", re.I)
SPARE_RE = re.compile(r"\b(?:spare|space)\b", re.I)
CKT_RE = re.compile(r"\b(\d{1,3})\b")


def _find_panel_anchors(page: fitz.Page, words: Optional[List[Tuple]] = None) -> List[Tuple[str, fitz.Rect]]:
    """
    Return [('K1', Rect), ('L1', Rect), ...] for this page.
    
    Detects panel anchors using multiple patterns:
    - Primary: "Panel:", "Panel", "PNL:", "Board:" followed by name (look ahead up to 3 tokens)
    - Secondary: "<NAME> PANEL SCHEDULE", "SCHEDULE - <NAME>"
    - Filters out sheet summaries: TOTALS, SUMMARY, LOAD, LOAD SUMMARY
    """
    if words is None:
        words = page.get_text("words", sort=True)  # (x0, y0, x1, y1, text, block, line, wno)
    anchors: List[Tuple[str, fitz.Rect]] = []
    
    # Sheet summary names to filter out
    SUMMARY_NAMES = {"TOTALS", "SUMMARY", "LOAD", "LOAD SUMMARY"}
    
    # Primary pattern: "Panel:", "Panel", "PNL:", "Board:" followed by name
    for i in range(len(words) - 1):
        x0, y0, x1, y1, txt, *_ = words[i]
        txt_lower = txt.lower().strip()
        
        if txt_lower in ["panel:", "panel", "pnl:", "pnl", "board:", "board"]:
            # Look ahead up to 3 tokens for panel name
            name = None
            name_rect = None
            for j in range(1, min(4, len(words) - i)):
                candidate = re.sub(r"[^\w\-\.]+", "", words[i + j][4]).upper()
                if candidate and candidate not in ["SCHEDULE", "SCHEDULES", "NAME", ""]:
                    name = candidate
                    name_rect = words[i + j]
                    break
            
            if name and name not in SUMMARY_NAMES:
                # Create a rect encompassing both anchor token and name
                rect = fitz.Rect(
                    min(x0, name_rect[0]),
                    min(y0, name_rect[1]),
                    max(x1, name_rect[2]),
                    max(y1, name_rect[3])
                )
                # Inflate by 2 points on each side
                rect.x0 -= 2
                rect.y0 -= 2
                rect.x1 += 2
                rect.y1 += 2
                anchors.append((name, rect))
    
    # Secondary pattern: "<NAME> PANEL SCHEDULE" or "SCHEDULE - <NAME>"
    for i in range(len(words) - 2):
        txt_lower = " ".join([w[4].lower() for w in words[i:i+3]])
        
        # Pattern: "<NAME> PANEL SCHEDULE"
        match = re.search(r"([A-Z0-9\-\.]+)\s+panel\s+schedule", txt_lower, re.IGNORECASE)
        if match:
            name = match.group(1).upper()
            if name not in SUMMARY_NAMES:
                # Use bounding rect of matched words
                matched_words = words[i:i+3]
                x0 = min(w[0] for w in matched_words)
                y0 = min(w[1] for w in matched_words)
                x1 = max(w[2] for w in matched_words)
                y1 = max(w[3] for w in matched_words)
                rect = fitz.Rect(x0 - 2, y0 - 2, x1 + 2, y1 + 2)
                anchors.append((name, rect))
        
        # Pattern: "SCHEDULE - <NAME>"
        match = re.search(r"schedule\s*-\s*([A-Z0-9\-\.]+)", txt_lower, re.IGNORECASE)
        if match:
            name = match.group(1).upper()
            if name not in SUMMARY_NAMES:
                matched_words = words[i:i+3]
                x0 = min(w[0] for w in matched_words)
                y0 = min(w[1] for w in matched_words)
                x1 = max(w[2] for w in matched_words)
                y1 = max(w[3] for w in matched_words)
                rect = fitz.Rect(x0 - 2, y0 - 2, x1 + 2, y1 + 2)
                anchors.append((name, rect))
    
    # Sort by position: top-to-bottom, then left-to-right
    anchors.sort(key=lambda a: (a[1].y0, a[1].x0))
    return anchors


def _group_rows(anchors: List[Tuple[str, fitz.Rect]], y_tol: float = 300.0) -> List[List[Tuple[str, fitz.Rect]]]:
    """Group anchors that sit on the same horizontal 'row'."""
    rows: List[List[Tuple[str, fitz.Rect]]] = []
    
    for a in anchors:
        if not rows or abs(a[1].y0 - rows[-1][0][1].y0) > y_tol:
            rows.append([a])
        else:
            rows[-1].append(a)
    
    # Sort each row by x position
    for r in rows:
        r.sort(key=lambda t: t[1].x0)
    
    return rows


def _calculate_overlap_area(rect1: fitz.Rect, rect2: fitz.Rect) -> float:
    """Calculate overlap area between two rectangles."""
    x_overlap = max(0, min(rect1.x1, rect2.x1) - max(rect1.x0, rect2.x0))
    y_overlap = max(0, min(rect1.y1, rect2.y1) - max(rect1.y0, rect2.y0))
    return x_overlap * y_overlap


def _shrink_rects_to_avoid_overlap(
    rects: List[Tuple[str, fitz.Rect]], threshold: float = 0.05, logger: Optional[logging.Logger] = None
) -> List[Tuple[str, fitz.Rect]]:
    """
    Shrink overlapping rectangles symmetrically until overlap is eliminated.
    
    Args:
        rects: List of (name, rect) tuples
        threshold: Overlap threshold as fraction of area (default 0.05 = 5%)
        logger: Optional logger for overlap warnings
    
    Returns:
        List of adjusted (name, rect) tuples
    """
    adjusted = [(name, fitz.Rect(rect)) for name, rect in rects]
    
    for i in range(len(adjusted)):
        for j in range(i + 1, len(adjusted)):
            name1, rect1 = adjusted[i]
            name2, rect2 = adjusted[j]
            
            overlap_area = _calculate_overlap_area(rect1, rect2)
            if overlap_area == 0:
                continue
            
            area1 = rect1.width * rect1.height
            area2 = rect2.width * rect2.height
            overlap_frac1 = overlap_area / area1 if area1 > 0 else 0
            overlap_frac2 = overlap_area / area2 if area2 > 0 else 0
            
            # If overlap exceeds threshold, shrink symmetrically
            if overlap_frac1 > threshold or overlap_frac2 > threshold:
                max_overlap_frac = max(overlap_frac1, overlap_frac2)
                if logger:
                    logger.warning(
                        f"overlap_adjusted: {name1} vs {name2} overlap={max_overlap_frac*100:.1f}%"
                    )
                
                # Calculate midpoint between rects
                mid_x = (rect1.x0 + rect1.x1 + rect2.x0 + rect2.x1) / 4.0
                
                # Shrink each rect toward its center, stopping at midpoint
                if rect1.x1 > mid_x:
                    shrink_amount = (rect1.x1 - mid_x) * 0.5
                    rect1.x1 -= shrink_amount
                if rect2.x0 < mid_x:
                    shrink_amount = (mid_x - rect2.x0) * 0.5
                    rect2.x0 += shrink_amount
                
                # Re-check overlap after adjustment
                new_overlap = _calculate_overlap_area(rect1, rect2)
                if new_overlap > 0:
                    # More aggressive shrink if still overlapping
                    if rect1.x1 > mid_x:
                        rect1.x1 = mid_x
                    if rect2.x0 < mid_x:
                        rect2.x0 = mid_x
    
    return adjusted


def _word_looks_like_panel_content(text: str) -> bool:
    """Heuristic to determine if a word likely belongs to panel table content."""
    if not text:
        return False
    txt = text.strip()
    if not txt:
        return False
    upper = txt.upper()
    if re.match(r"^\d{1,3}$", upper):
        return True
    if re.match(r"^\d{1,3}[A-Z]?$", upper):
        return True
    if re.match(r"^\d{1,3}\s*(?:A|AMP|AMPS|VA|W|KW|KVA)$", upper):
        return True
    if upper in {"CKT", "CIRCUIT", "TOTAL", "SUMMARY", "LOAD", "LOADS", "PHASE"}:
        return True
    if upper in {"A", "B", "C", "A/B", "B/C", "A/C"}:
        return True
    if any(token in upper for token in ("VA", "KW", "AMP", "LOAD")):
        return True
    return False


def _extend_panel_bottom_with_content(
    words: List[Tuple],
    *,
    x_left: float,
    x_right: float,
    y_top: float,
    default_bottom: float,
    pad: float,
    page_bottom: float,
) -> float:
    """Extend panel bottom boundary based on detected table content."""
    y_bottom = max(default_bottom, y_top + pad * 2)
    band_left = x_left - pad
    band_right = x_right + pad
    for x0, y0, x1, y1, text, *_ in words:
        if y0 <= y_top:
            continue
        if x1 < band_left or x0 > band_right:
            continue
        if not _word_looks_like_panel_content(text):
            continue
        y_bottom = max(y_bottom, min(page_bottom, y1 + pad))
    return min(y_bottom, page_bottom)


def segment_panels(
    page: fitz.Page, *, y_tol: Optional[float] = None, pad: float = 10.0, logger: Optional[logging.Logger] = None
) -> List[Tuple[str, fitz.Rect]]:
    """
    Segment panels from a page with adaptive y_tol and overlap resolution.
    
    Args:
        page: PyMuPDF page object
        y_tol: Tolerance for grouping headers into rows (auto-computed if None)
        pad: Padding to add around panel boundaries
    
    Returns:
        List of (panel_name, rectangle) tuples with no overlaps
    """
    page_rect = page.rect
    
    # Compute adaptive y_tol if not provided
    if y_tol is None:
        y_tol = min(120.0, page_rect.height * 0.08)
    
    words = page.get_text("words", sort=True)
    anchors = _find_panel_anchors(page, words=words)
    if not anchors:
        return []
    
    rows = _group_rows(anchors, y_tol=y_tol)
    
    rects: List[Tuple[str, fitz.Rect]] = []
    for r_idx, row in enumerate(rows):
        # Vertical bounds: from this row's headers down to halfway to next row
        y_top = max(page_rect.y0, min(a[1].y0 for a in row) - 3 * pad)
        
        # Bottom boundary: halfway to next row's headers, or page bottom
        # For last row, ensure we capture full height by going to page bottom
        if r_idx + 1 < len(rows):
            next_row_top = min(a[1].y0 for a in rows[r_idx + 1])
            gap = max(0.0, next_row_top - y_top)
            # Use 90% of distance to next row to capture more content without bleeding
            y_bottom = min(page_rect.y1, y_top + gap * 0.9)
        else:
            # Last row: go to page bottom, but ensure we don't cut off content
            # Look for text blocks below the anchor to determine actual panel height
            y_bottom = page_rect.y1
            # Try to detect actual panel content extent by looking for circuit numbers
            # below the anchor (circuits typically extend well below the header)
            words = page.get_text("words", sort=True)
            max_y_for_row = max(a[1].y1 for a in row)
            # Find the maximum y-coordinate of text that could belong to this row's panels
            for word in words:
                word_y = word[1]  # y0 of word
                # If word is below anchor row and within reasonable horizontal bounds
                if word_y > max_y_for_row and word_y < page_rect.y1:
                    # Check if word is horizontally aligned with any panel in this row
                    for name, a_rect in row:
                        if a_rect.x0 - 50 <= word[0] <= a_rect.x1 + 50:
                            # Potential panel content - extend bottom boundary
                            y_bottom = max(y_bottom, word[3] + pad)  # word[3] is y1
                            break
        
        # Horizontal bounds per panel: midpoints between neighbors
        for j, (name, a_rect) in enumerate(row):
            x_left = page_rect.x0 if j == 0 else (row[j - 1][1].x0 + a_rect.x0) / 2.0
            x_right = (
                page_rect.x1
                if j == len(row) - 1
                else (a_rect.x0 + row[j + 1][1].x0) / 2.0
            )
            panel_y_bottom = _extend_panel_bottom_with_content(
                words,
                x_left=x_left,
                x_right=x_right,
                y_top=y_top,
                default_bottom=y_bottom,
                pad=pad,
                page_bottom=page_rect.y1 - pad,
            )
            rect = fitz.Rect(
                x_left + pad, y_top + 2 * pad, x_right - pad, panel_y_bottom
            )
            
            # Log panel dimensions for debugging
            if logger:
                logger.debug(
                    f"panel_segmented: {name} rect=[{rect.x0:.1f},{rect.y0:.1f},"
                    f"{rect.x1:.1f},{rect.y1:.1f}] height={rect.height:.1f}"
                )
            
            rects.append((name, rect))
    
    # Resolve overlaps
    rects = _shrink_rects_to_avoid_overlap(rects, threshold=0.05, logger=logger)
    
    return rects


def panel_rects(page: fitz.Page, y_tol: float = 300.0, pad: float = 10.0) -> List[Tuple[str, fitz.Rect]]:
    """
    Compute a rectangle per panel using row/column midpoints.
    Works for 1xN, 2x2, etc. panel grids like your sheet.
    
    Args:
        page: PyMuPDF page object
        y_tol: Tolerance for grouping headers into rows
        pad: Padding to add around panel boundaries
    
    Returns:
        List of (panel_name, rectangle) tuples
    """
    page_rect = page.rect
    anchors = _find_panel_anchors(page)
    if not anchors:
        return []
    
    rows = _group_rows(anchors, y_tol=y_tol)
    
    rects: List[Tuple[str, fitz.Rect]] = []
    for r_idx, row in enumerate(rows):
        # Vertical bounds of this row: from this row's headers down to halfway to next row
        y_top = max(page_rect.y0, min(a[1].y0 for a in row) - 3 * pad)
        # For bottom boundary, go halfway to next row's headers, or use page bottom
        if r_idx + 1 < len(rows):
            next_row_top = min(a[1].y0 for a in rows[r_idx + 1])
            y_bottom = y_top + (next_row_top - y_top) / 2.0
        else:
            y_bottom = page_rect.y1
        
        # Horizontal bounds per panel: midpoints to neighbors
        for j, (name, a_rect) in enumerate(row):
            x_left = page_rect.x0 if j == 0 else (row[j - 1][1].x0 + a_rect.x0) / 2.0
            x_right = page_rect.x1 if j == len(row) - 1 else (a_rect.x0 + row[j + 1][1].x0) / 2.0
            rect = fitz.Rect(x_left + pad, y_top + 2 * pad, x_right - pad, y_bottom - pad)
            rects.append((name, rect))
    
    return rects


def normalize_left_right(rows: List[dict]) -> List[dict]:
    """
    Fix odd/even left/right swaps in panel circuit data.
    Ensures odd circuit numbers are on the left, even on the right.
    """
    out = []
    for row in rows:
        left_no = row.get("circuit_number")
        right = row.get("right_side") or {}
        right_no = right.get("circuit_number")
        
        # Swap if even is on the left and odd on the right
        if left_no and right_no and left_no % 2 == 0 and right_no % 2 == 1:
            # Save left side data
            left_snapshot = {
                k: row.get(k) 
                for k in ("circuit_number", "load_classification", "load_name", 
                         "trip", "poles", "phase_loads")
            }
            # Move right to left
            row["circuit_number"] = right.get("circuit_number")
            row["load_classification"] = right.get("load_classification")
            row["load_name"] = right.get("load_name")
            row["trip"] = right.get("trip")
            row["poles"] = right.get("poles")
            row["phase_loads"] = right.get("phase_loads")
            # Move left to right
            row["right_side"] = left_snapshot
            
        # If only left exists and it's even, move it to right
        elif left_no and not right_no and left_no % 2 == 0:
            row["right_side"] = {
                "circuit_number": left_no,
                "load_classification": row.get("load_classification"),
                "load_name": row.get("load_name"),
                "trip": row.get("trip"),
                "poles": row.get("poles"),
                "phase_loads": row.get("phase_loads"),
            }
            # Clear left side
            row["circuit_number"] = None
            row["load_classification"] = None
            row["load_name"] = None
            row["trip"] = None
            row["poles"] = None
            row["phase_loads"] = {"A": None, "B": None, "C": None}
            
        out.append(row)
    
    return out


def detect_column_headers(
    page: fitz.Page, clip: fitz.Rect, header_band_px: float = 150.0
) -> Dict[str, float]:
    """
    Detect column headers and their x-positions to reduce column drift.
    
    Args:
        page: PyMuPDF page object
        clip: Rectangle to search within
        header_band_px: Height of header band to search (default 150pt from top)
    
    Returns:
        Dictionary mapping column names to x-positions
    """
    # Limit search to header band (top portion of clip)
    header_clip = fitz.Rect(
        clip.x0, clip.y0, clip.x1, min(clip.y1, clip.y0 + header_band_px)
    )
    
    words = page.get_text("words", clip=header_clip, sort=True)
    headers = {}
    for x0, y0, x1, y1, txt, *_ in words:
        txt_upper = txt.upper().strip()
        for col_name, pattern in HEADER_PATTERNS.items():
            if re.match(pattern, txt_upper, re.IGNORECASE):
                # Store the center x position
                headers[col_name] = (x0 + x1) / 2.0
                break
    
    return headers


def compute_left_right_split(
    page: fitz.Page,
    rect: fitz.Rect,
    *,
    header_band_px: float,
    max_header_band_px: Optional[float] = None,
    near_center_bias: float = 0.35,
) -> Tuple[fitz.Rect, fitz.Rect, float]:
    """
    Split a panel rectangle into left/right halves using detected header positions.
    """
    band_height = header_band_px
    if max_header_band_px is not None:
        band_height = min(band_height, max_header_band_px)
    header_clip = fitz.Rect(rect.x0, rect.y0, rect.x1, min(rect.y1, rect.y0 + band_height))
    words = page.get_text("words", clip=header_clip, sort=True)

    header_positions: List[float] = []
    for x0, _, x1, _, txt, *_ in words:
        txt_upper = txt.upper().strip()
        for pattern in HEADER_PATTERNS.values():
            if re.match(pattern, txt_upper, re.IGNORECASE):
                header_positions.append((x0 + x1) / 2.0)
                break

    mid_x = (rect.x0 + rect.x1) / 2.0
    split_x = mid_x
    rect_half = max(1.0, rect.width / 2.0)

    if len(header_positions) >= 2:
        header_positions.sort()
        best_score = None
        best_split = mid_x
        for i in range(len(header_positions) - 1):
            left = header_positions[i]
            right = header_positions[i + 1]
            gap = right - left
            if gap < 5:
                continue
            candidate = (left + right) / 2.0
            center_offset = abs(candidate - mid_x) / rect_half
            score = gap * (1.0 - near_center_bias * center_offset)
            if best_score is None or score > best_score:
                best_score = score
                best_split = candidate
        if best_score is not None:
            split_x = best_split
        else:
            split_x = header_positions[len(header_positions) // 2]
    elif len(header_positions) == 1:
        only = header_positions[0]
        if only > mid_x:
            split_x = (only + rect.x0) / 2.0
        else:
            split_x = (only + rect.x1) / 2.0

    split_x = max(rect.x0 + 1.0, min(rect.x1 - 1.0, split_x))
    left_rect = fitz.Rect(rect.x0, rect.y0, split_x, rect.y1)
    right_rect = fitz.Rect(split_x, rect.y0, rect.x1, rect.y1)
    return left_rect, right_rect, split_x


def get_panel_text_blocks(page: fitz.Page, clip: fitz.Rect) -> str:
    """
    Get text from a clipped region using block extraction for better structure.
    
    Args:
        page: PyMuPDF page object
        clip: Rectangle to extract text from
    
    Returns:
        Concatenated text from all blocks in the region
    """
    blocks = page.get_text("blocks", clip=clip, sort=True)
    # Join block texts with newlines
    return "\n".join(block[4] for block in blocks if block[4].strip())


def map_values_to_columns(
    words: List[Tuple], headers: Dict[str, float], tolerance: float = 30.0
) -> Dict[int, Dict[str, str]]:
    """
    Map extracted words to their appropriate columns based on header positions.
    Reduces column drift by assigning values to nearest column header.
    
    Args:
        words: List of word tuples from PyMuPDF
        headers: Dictionary of column names to x-positions
        tolerance: Maximum x-distance to associate with a column
    
    Returns:
        Dictionary of row_num -> {column: value}
    """
    if not headers:
        return {}
    
    rows = {}
    current_row = -1
    last_y = None
    
    for x0, y0, x1, y1, text, *_ in words:
        # Detect new row based on y position change
        if last_y is None or abs(y0 - last_y) > 5:
            current_row += 1
            rows[current_row] = {}
            last_y = y0
        
        # Find nearest column header
        word_center = (x0 + x1) / 2.0
        best_col = None
        best_dist = float('inf')
        
        for col_name, col_x in headers.items():
            dist = abs(word_center - col_x)
            if dist < best_dist and dist < tolerance:
                best_dist = dist
                best_col = col_name
        
        if best_col:
            # Append to existing value if column already has text
            if best_col in rows[current_row]:
                rows[current_row][best_col] += " " + text
            else:
                rows[current_row][best_col] = text
    
    return rows


def extract_panel_with_column_mapping(
    page: fitz.Page, panel_name: str, rect: fitz.Rect
) -> Dict[str, Any]:
    """
    Extract panel with column drift protection using header detection.
    
    Args:
        page: PyMuPDF page object
        panel_name: Name of the panel
        rect: Rectangle defining panel boundaries
    
    Returns:
        Dictionary with panel data including mapped rows
    """
    # Detect column headers
    headers = detect_column_headers(page, rect)
    
    # Get words within panel
    words = page.get_text("words", clip=rect, sort=True)
    
    # Map values to columns
    mapped_rows = map_values_to_columns(words, headers)
    
    # Also get block text for fallback
    block_text = get_panel_text_blocks(page, rect)
    
    return {
        "panel_name": panel_name,
        "headers": headers,
        "mapped_rows": mapped_rows,
        "raw_text": block_text
    }


def _normalize_bbox(bbox: Tuple[float, float, float, float], page_rect: Optional[fitz.Rect]) -> Optional[List[float]]:
    """Normalize bounding box coordinates to [0, 1] range relative to page."""
    if not page_rect:
        return None
    width = max(page_rect.width, 1.0)
    height = max(page_rect.height, 1.0)
    return [
        round((bbox[0] - page_rect.x0) / width, 6),
        round((bbox[1] - page_rect.y0) / height, 6),
        round((bbox[2] - page_rect.x0) / width, 6),
        round((bbox[3] - page_rect.y0) / height, 6),
    ]


def _words_to_lines(words: List[Tuple], page_rect: Optional[fitz.Rect]) -> List[Dict[str, Any]]:
    """Group words into lines based on block/line numbers."""
    grouped: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for x0, y0, x1, y1, text, block, line, *_ in words:
        key = (block, line)
        entry = grouped.setdefault(
            key,
            {
                "text_parts": [],
                "min_x": x0,
                "max_x": x1,
                "min_y": y0,
                "max_y": y1,
            },
        )
        entry["text_parts"].append(text)
        entry["min_x"] = min(entry["min_x"], x0)
        entry["max_x"] = max(entry["max_x"], x1)
        entry["min_y"] = min(entry["min_y"], y0)
        entry["max_y"] = max(entry["max_y"], y1)

    lines: List[Dict[str, Any]] = []
    for entry in grouped.values():
        text = " ".join(entry["text_parts"]).strip()
        if not text:
            continue
        bbox = (entry["min_x"], entry["min_y"], entry["max_x"], entry["max_y"])
        cx = (entry["min_x"] + entry["max_x"]) / 2.0
        cy = (entry["min_y"] + entry["max_y"]) / 2.0
        lines.append(
            {
                "text": text,
                "cx": cx,
                "cy": cy,
                "bbox": bbox,
                "bbox_norm": _normalize_bbox(bbox, page_rect),
            }
        )
    lines.sort(key=lambda item: (item["cy"], item["cx"]))
    return lines


def _is_circuit_line(text: str) -> bool:
    """Determine if a line represents a circuit row."""
    if not text:
        return False
    if not AMP_RE.search(text):
        return False
    if VA_RE.search(text) or SPARE_RE.search(text):
        return True
    return False


def _assign_panel_to_lines(
    lines: List[Dict[str, Any]], headers: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Assign circuit lines to nearest panel header based on coordinates."""
    results: List[Dict[str, Any]] = []
    if not headers:
        return results

    for line in lines:
        if not _is_circuit_line(line["text"]):
            continue
        candidates = [
            header
            for header in headers
            if line["cy"] >= header["cy"] - 5.0
        ]
        if not candidates:
            continue

        def _score(header: Dict[str, Any]) -> float:
            dy = max(0.0, line["cy"] - header["cy"])
            dx = abs(line["cx"] - header["cx"])
            return dy * dy + (dx * 0.5) ** 2

        owner = min(candidates, key=_score)
        results.append({**line, "panel_id": owner["panel_id"]})
    return results


def _extract_circuit_number(text: str) -> Optional[int]:
    """Extract circuit number from text, avoiding amps/VA values."""
    candidates: List[int] = []
    for match in CKT_RE.finditer(text):
        tail = text[match.end() : match.end() + 4]
        if re.match(r"\s*(?:A|AMP|AMPS|VA|KVA|KW)\b", tail, re.I):
            continue
        try:
            candidates.append(int(match.group(1)))
        except ValueError:
            continue
    if not candidates:
        return None
    return min(candidates)


def build_panel_row_hints(page: fitz.Page, words: List[Tuple]) -> List[Dict[str, Any]]:
    """
    Build panel row hints by detecting panel headers and assigning circuit rows.
    
    Args:
        page: PyMuPDF page object
        words: List of word tuples from page.get_text("words", sort=True)
    
    Returns:
        List of panel dictionaries with panel_id, cx, cy, and rows
    """
    if not words:
        return []

    anchors = _find_panel_anchors(page, words=words)
    if not anchors:
        return []

    page_rect = getattr(page, "rect", None)
    lines = _words_to_lines(words, page_rect)
    headers = [
        {
            "panel_id": name,
            "cx": (rect.x0 + rect.x1) / 2.0,
            "cy": (rect.y0 + rect.y1) / 2.0,
        }
        for name, rect in anchors
    ]
    assigned = _assign_panel_to_lines(lines, headers)
    if not assigned:
        return []

    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for line in assigned:
        grouped[line["panel_id"]].append(
            {
                "text": line["text"],
                "ckt": _extract_circuit_number(line["text"]),
                "cx": line["cx"],
                "cy": line["cy"],
                "bbox": line.get("bbox"),
                "bbox_norm": line.get("bbox_norm"),
            }
        )

    header_lookup = {header["panel_id"]: header for header in headers}
    panels: List[Dict[str, Any]] = []
    for panel_id, rows in grouped.items():
        rows.sort(key=lambda row: ((row["ckt"] if row["ckt"] is not None else 9999), row["cy"]))
        header = header_lookup.get(panel_id, {})
        panels.append(
            {
                "panel_id": panel_id,
                "cx": header.get("cx"),
                "cy": header.get("cy"),
                "rows": rows,
            }
        )

    panels.sort(key=lambda panel: (panel.get("cy") if panel.get("cy") is not None else float("inf"), panel["panel_id"]))
    return panels
