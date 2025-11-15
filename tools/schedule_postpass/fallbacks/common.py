"""Common utilities for discipline fallback iterators."""
from __future__ import annotations

import re
from typing import Any, Dict, Optional


def ci_get(mapping: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Case-insensitive dict get."""
    if not isinstance(mapping, dict):
        return default
    target = key.lower()
    for k, v in mapping.items():
        if isinstance(k, str) and k.lower() == target:
            return v
    return default


def first_non_empty(*values: Any) -> Optional[Any]:
    """Return the first non-empty (trimmed) string or first non-None value."""
    for v in values:
        if isinstance(v, str):
            s = v.strip()
            if s:
                return s
        elif v is not None:
            return v
    return None


def is_numeric_phase_value(value: Any) -> bool:
    """
    Check if a phase load value is numeric (e.g., '540 VA', '20 A') rather than descriptive text.
    
    This is useful for extracting descriptive text from phase_loads structures where
    some values may be numeric measurements and others may be descriptive labels.
    """
    if not isinstance(value, str):
        return False
    value = value.strip()
    # Match patterns like "540 VA", "20 A", "0 VA", "--", or pure numbers
    if value in ("--", ""):
        return True
    # Match numeric patterns with optional units
    return bool(re.match(r"^\d+(?:\.\d+)?\s*(?:VA|A|W)?$", value, re.IGNORECASE))


def extract_text_from_phase_loads(phase_loads: Any) -> Optional[str]:
    """
    Extract descriptive text from phase_loads dict, skipping numeric values.
    
    This function looks through phase_loads (typically a dict with "A", "B", "C" keys)
    and returns the first non-numeric value found, which is likely descriptive text
    (e.g., "MV-400 (Surge Protector)") rather than a measurement.
    
    Returns None if no descriptive text is found.
    """
    if not isinstance(phase_loads, dict):
        return None
    for phase in ["A", "B", "C"]:
        value = phase_loads.get(phase)
        if value and not is_numeric_phase_value(value):
            # Found descriptive text (e.g., "MV-400 (Surge Protector)")
            return str(value).strip()
    return None

