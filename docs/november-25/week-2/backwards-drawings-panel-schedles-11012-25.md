Easiest fix (minimal patch, PyMuPDF only)

What it does

Find every Panel: <NAME> header on the page.

Turn those headers into panel rectangles using simple “row/column” midpoints.

For each rectangle, call your existing panel parser on clip=rect.

(Optional) Apply a tiny odd/even “flip‑guard” so left/right rows don’t swap.

This keeps your current logic; you’re just feeding it one panel at a time.

Drop‑in helper (≈50 lines)
# minimal_panel_clip.py
from __future__ import annotations
import re
from typing import List, Tuple
import fitz  # PyMuPDF

def _find_panel_anchors(page: fitz.Page) -> List[Tuple[str, fitz.Rect]]:
    """Return [('K1', Rect), ('L1', Rect), ...] for this page."""
    words = page.get_text("words", sort=True)  # (x0, y0, x1, y1, text, block, line, wno)
    anchors: List[Tuple[str, fitz.Rect]] = []
    for i in range(len(words) - 1):
        x0, y0, x1, y1, txt, *_ = words[i]
        if txt.lower() == "panel:":
            name = re.sub(r"[^\w\-]+", "", words[i + 1][4]).upper()
            rect = fitz.Rect(x0, y0, max(x1, words[i + 1][2]), max(y1, words[i + 1][3])).inflate(2, 2)
            anchors.append((name, rect))
    anchors.sort(key=lambda a: (a[1].y0, a[1].x0))  # top-to-bottom, then left-to-right
    return anchors

def _group_rows(anchors: List[Tuple[str, fitz.Rect]], y_tol: float = 18.0):
    """Group anchors that sit on the same horizontal 'row'."""
    rows: List[List[Tuple[str, fitz.Rect]]] = []
    for a in anchors:
        if not rows or abs(a[1].y0 - rows[-1][0][1].y0) > y_tol:
            rows.append([a])
        else:
            rows[-1].append(a)
    for r in rows:
        r.sort(key=lambda t: t[1].x0)
    return rows

def panel_rects(page: fitz.Page, y_tol: float = 18.0, pad: float = 10.0) -> List[Tuple[str, fitz.Rect]]:
    """
    Compute a rectangle per panel using row/column midpoints.
    Works for 1xN, 2x2, etc. panel grids like your sheet.
    """
    page_rect = page.rect
    anchors = _find_panel_anchors(page)
    if not anchors:
        return []
    rows = _group_rows(anchors, y_tol=y_tol)

    rects: List[Tuple[str, fitz.Rect]] = []
    for r_idx, row in enumerate(rows):
        # vertical bounds of this row: from this row's headers down to halfway to next row
        y_top = max(page_rect.y0, min(a[1].y0 for a in row) - 3 * pad)
        y_bottom = (y_top + min(a[1].y0 for a in rows[r_idx + 1])) / 2.0 if r_idx + 1 < len(rows) else page_rect.y1

        # horizontal bounds per panel: midpoints to neighbors
        for j, (name, a_rect) in enumerate(row):
            x_left = page_rect.x0 if j == 0 else (row[j - 1][1].x0 + a_rect.x0) / 2.0
            x_right = page_rect.x1 if j == len(row) - 1 else (a_rect.x0 + row[j + 1][1].x0) / 2.0
            rect = fitz.Rect(x_left + pad, y_top + 2 * pad, x_right - pad, y_bottom - pad)
            rects.append((name, rect))
    return rects

# Optional: fix odd/even left/right swaps after your parse
def normalize_left_right(rows: List[dict]) -> List[dict]:
    out = []
    for row in rows:
        left_no = row.get("circuit_number")
        right = row.get("right_side") or {}
        right_no = right.get("circuit_number")
        # swap if even is on the left and odd on the right
        if left_no and right_no and left_no % 2 == 0 and right_no % 2 == 1:
            left_snapshot = {k: row.get(k) for k in ("circuit_number", "load_classification","load_name","trip","poles","phase_loads")}
            row["circuit_number"] = right.get("circuit_number")
            row["load_classification"] = right.get("load_classification")
            row["load_name"] = right.get("load_name")
            row["trip"] = right.get("trip")
            row["poles"] = right.get("poles")
            row["phase_loads"] = right.get("phase_loads")
            row["right_side"] = left_snapshot
        # if only left exists and it's even, move it to right
        elif left_no and not right_no and left_no % 2 == 0:
            row["right_side"] = {
                "circuit_number": left_no,
                "load_classification": row.get("load_classification"),
                "load_name": row.get("load_name"),
                "trip": row.get("trip"),
                "poles": row.get("poles"),
                "phase_loads": row.get("phase_loads"),
            }
            row["circuit_number"] = None
            row["load_classification"] = None
            row["load_name"] = None
            row["trip"] = None
            row["poles"] = None
            row["phase_loads"] = {"A": None, "B": None, "C": None}
        out.append(row)
    return out

Call it around your existing parser
import fitz
from minimal_panel_clip import panel_rects, normalize_left_right

def extract_panels(pdf_path: str):
    doc = fitz.open(pdf_path)
    panels_out = []
    for page in doc:
        for name, rect in panel_rects(page):
            # Only extract text inside this panel’s box — no cross‑panel bleed
            panel_text = page.get_text("text", clip=rect, sort=True)
            rows = parse_your_existing_panel_text(panel_text)  # your current logic
            rows = normalize_left_right(rows)                  # optional but recommended
            panels_out.append({"panel_name": name, "circuits": rows})
    return {"ELECTRICAL": {"panels": panels_out}}


That’s the whole change. Because you’re now clipping to each panel’s rectangle, K1 rows can’t leak into L1/H1/K1S, which is exactly the problem on E5.00.

Why this is accurate enough (without overengineering)

Uses what’s already in your PDF: the “Panel: H1 / K1 / L1 / K1S” headers and the fact they’re printed in distinct boxes (top‑left, top‑right, bottom‑left, bottom‑right on your sheet).

Zero external services: just PyMuPDF.

Minimal surface area: you keep your parser; the patch only gates input by region and fixes odd/even flips.

Two optional 1‑liners for more robustness (still simple)

If your parser reads by blocks: page.get_text("blocks", clip=rect, sort=True) → join the block texts and feed that to the same parser.

To reduce “column drift”: detect the header line inside the clipped region (e.g., CKT, Load Name, Trip, Poles, A/B/C) and remember the x of each header word; when you map row tokens, drop them into the nearest header x. That’s <30 lines and avoids values landing in the wrong column.