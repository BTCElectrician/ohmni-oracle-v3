"""
Minimal panel clipping utility for electrical panel schedule extraction.
This module provides functionality to detect and clip individual panels
from PDF pages to prevent cross-panel text bleeding.
"""
from __future__ import annotations
import re
from typing import List, Tuple, Optional, Dict
import fitz  # PyMuPDF


def _find_panel_anchors(page: fitz.Page) -> List[Tuple[str, fitz.Rect]]:
    """Return [('K1', Rect), ('L1', Rect), ...] for this page."""
    words = page.get_text("words", sort=True)  # (x0, y0, x1, y1, text, block, line, wno)
    anchors: List[Tuple[str, fitz.Rect]] = []
    
    for i in range(len(words) - 1):
        x0, y0, x1, y1, txt, *_ = words[i]
        # More flexible panel detection
        if txt.lower() in ["panel:", "panel", "pnl:", "pnl", "board:", "board"]:
            # Get the panel name from the next word
            name = re.sub(r"[^\w\-]+", "", words[i + 1][4]).upper()
            # Skip if name is too generic
            if name in ["SCHEDULE", "SCHEDULES", "NAME", ""]:
                continue
            # Create a rect encompassing both "Panel:" and the name
            rect = fitz.Rect(x0, y0, max(x1, words[i + 1][2]), max(y1, words[i + 1][3]))
            # Manually inflate the rect by 2 points on each side
            rect.x0 -= 2
            rect.y0 -= 2
            rect.x1 += 2
            rect.y1 += 2
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


def detect_column_headers(page: fitz.Page, clip: fitz.Rect) -> Dict[str, float]:
    """
    Detect column headers and their x-positions to reduce column drift.
    
    Args:
        page: PyMuPDF page object
        clip: Rectangle to search within
    
    Returns:
        Dictionary mapping column names to x-positions
    """
    words = page.get_text("words", clip=clip, sort=True)
    header_patterns = {
        "CKT": r"^(CKT|CIRCUIT)$",
        "LOAD_NAME": r"^(LOAD\s*NAME|DESCRIPTION)$",
        "TRIP": r"^(TRIP|BKR)$",
        "POLES": r"^(POLES?|P)$",
        "PHASE_A": r"^(A|PHASE\s*A)$",
        "PHASE_B": r"^(B|PHASE\s*B)$",
        "PHASE_C": r"^(C|PHASE\s*C)$",
    }
    
    headers = {}
    for x0, y0, x1, y1, txt, *_ in words:
        txt_upper = txt.upper().strip()
        for col_name, pattern in header_patterns.items():
            if re.match(pattern, txt_upper, re.IGNORECASE):
                # Store the center x position
                headers[col_name] = (x0 + x1) / 2.0
                break
    
    return headers


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
