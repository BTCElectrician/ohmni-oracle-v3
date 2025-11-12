"""Common utilities for discipline fallback iterators."""
from __future__ import annotations

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

