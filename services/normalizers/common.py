"""
Common normalization utilities shared across domain modules.
"""
import re
from typing import Any, Optional


def safe_int(value: Any) -> Optional[int]:
    """Convert various value types to int if possible."""
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        try:
            return int(value)
        except Exception:
            return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        match = re.search(r"-?\d+", stripped)
        if match:
            try:
                return int(match.group(0))
            except Exception:
                return None
    return None


def extract_numeric_value(value_str: str) -> float:
    """Extract numeric value from a string, handling common units."""
    if not isinstance(value_str, str):
        return value_str

    # Remove non-numeric characters except decimals
    numeric_chars = re.sub(r"[^\d.]", "", value_str)

    # Return as float if possible
    try:
        if numeric_chars:
            return float(numeric_chars)
    except ValueError:
        pass

    return value_str

