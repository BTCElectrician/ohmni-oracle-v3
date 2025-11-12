"""Document ID generation and key sanitization utilities."""
from __future__ import annotations

import re
from typing import Any, Dict


_KEY_SANITIZE_REGEX = re.compile(r"[^A-Za-z0-9_\-=]")
_BOGUS_ROOM_PATTERNS = [
    re.compile(r"^\s*ps[\s_\-]*\d+\s*$", re.IGNORECASE),
    re.compile(r"\barea\s+not\s+in\s+scope\b", re.IGNORECASE),
    re.compile(r"^\s*ada\s*$", re.IGNORECASE),
]


def sanitize_key_component(value: Any, fallback: str = "none") -> str:
    """Sanitize a single component for use in document IDs."""
    text = str(value or "").strip()
    if not text:
        text = fallback
    sanitized = _KEY_SANITIZE_REGEX.sub("-", text)
    sanitized = re.sub("-+", "-", sanitized)
    sanitized = sanitized.strip("-")
    return sanitized or fallback


def make_document_id(*parts: Any) -> str:
    """Generate a stable document ID from multiple parts."""
    components = [sanitize_key_component(part) for part in parts if str(part or "").strip()]
    if not components:
        return "doc"
    return "-".join(components)


def leftpad_circuit(value: Any) -> str:
    """Left-pad circuit numbers to 3 digits for stable sorting."""
    try:
        return f"{int(str(value).strip()):03d}"
    except Exception:
        return str(value)


def stable_key(schedule_type: str, key_obj: Dict[str, Any]) -> str:
    """Generate a stable key string from schedule type and key object."""
    parts = [schedule_type]
    for name in sorted(key_obj.keys()):
        val = key_obj[name]
        if name == "circuit":
            val = leftpad_circuit(val)
        parts.append(f"{name}-{val}")
    return "_".join(parts)


def _is_bogus_room(room: Dict[str, Any]) -> bool:
    """Check if a room entry should be filtered out as bogus."""
    name_candidates = [
        str(room.get("room_name") or "").strip(),
        str(room.get("room_number") or "").strip(),
        str(room.get("room_id") or "").strip(),
    ]
    for name in name_candidates:
        if not name:
            continue
        for pat in _BOGUS_ROOM_PATTERNS:
            if pat.search(name):
                return True
    return False

