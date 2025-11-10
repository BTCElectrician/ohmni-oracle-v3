"""Helpers for building deterministic storage paths."""

import os
import re
from typing import Tuple


_REVISION_PATTERN = re.compile(r"(?:rev(?:ision)?)[\s._-]*([A-Za-z0-9]+)", re.IGNORECASE)


def slugify_storage_component(value: str, fallback: str = "general") -> str:
    """Convert a string into a lower-case, hyphenated storage-safe slug."""
    if not value:
        return fallback

    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.strip().lower())
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug or fallback


def _extract_revision_token(filename: str) -> str:
    match = _REVISION_PATTERN.search(filename or "")
    if not match:
        return ""
    token = re.sub(r"[^A-Za-z0-9]", "", match.group(1))
    return token.lower()


def derive_drawing_identifiers(filename: str) -> Tuple[str, str]:
    """Return a tuple of (drawing_slug, version_folder) for storage paths."""
    base_name = os.path.splitext(filename or "drawing")[0]

    revision_token = _extract_revision_token(base_name)
    version_folder = f"v{revision_token}" if revision_token else "v1"

    base_without_revision = _REVISION_PATTERN.sub("", base_name)
    drawing_slug = slugify_storage_component(base_without_revision, fallback="drawing")

    return drawing_slug, version_folder

