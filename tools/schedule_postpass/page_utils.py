"""Page number inference utilities for ETL document generation."""
from __future__ import annotations

from typing import Any, Dict


def infer_page(raw_json: Dict[str, Any]) -> int:
    """
    Infer the PDF page number from raw structured JSON.
    
    Checks multiple keys in order of preference:
    1. page_number (canonical field persisted by pipeline)
    2. page (alternative field name)
    3. sheet_index (legacy field name)
    4. DRAWING_METADATA.page_number or DRAWING_METADATA.page
    
    Returns 1-based page number, defaulting to 1 if no valid value found.
    
    Args:
        raw_json: Raw structured JSON from pipeline output
        
    Returns:
        Integer page number (1-based, minimum 1)
    """
    # Check top-level keys first (prefer page_number from pipeline)
    for key in ("page_number", "page", "sheet_index"):
        value = raw_json.get(key)
        if isinstance(value, int) and value > 0:
            return value
        try:
            parsed = int(str(value).strip())
            if parsed > 0:
                return parsed
        except Exception:
            continue
    
    # Check DRAWING_METADATA if present
    drawing_meta = raw_json.get("DRAWING_METADATA") or raw_json.get("drawing_metadata")
    if isinstance(drawing_meta, dict):
        for key in ("page_number", "page", "sheet_index"):
            value = drawing_meta.get(key)
            if isinstance(value, int) and value > 0:
                return value
            try:
                parsed = int(str(value).strip())
                if parsed > 0:
                    return parsed
            except Exception:
                continue
    
    # Default to page 1 if no hints found
    return 1

