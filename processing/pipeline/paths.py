"""
Path utilities for building storage names and formatting paths.
"""
import os
from datetime import datetime
from typing import Optional

from utils.storage_utils import slugify_storage_component


def build_archive_storage_name(
    storage_discipline: str,
    drawing_slug: str,
    file_name: str,
) -> str:
    """Build a storage path for the archived original document."""
    components = [
        storage_discipline,
        drawing_slug,
        file_name,
    ]
    return "/".join(filter(None, components))


def build_structured_storage_name(
    storage_discipline: str,
    drawing_slug: str,
    structured_output_path: str,
) -> str:
    """Build a storage path for the structured JSON output."""
    output_name = os.path.basename(structured_output_path)
    components = [
        storage_discipline,
        drawing_slug,
        "structured",
        output_name,
    ]
    return "/".join(filter(None, components))


def build_artifact_storage_name(
    storage_discipline: str,
    drawing_slug: str,
    filename: str,
    artifact_type: str,
) -> str:
    """Build a storage path for additional structured artifacts (templates, OCR, etc.)."""
    components = [
        storage_discipline,
        drawing_slug,
        artifact_type,
        filename,
    ]
    return "/".join(filter(None, components))


def relative_to_output_root(path: Optional[str], output_base_folder: str) -> Optional[str]:
    """Return a path relative to the configured output root for readability."""
    if not path:
        return None
    try:
        return os.path.relpath(path, output_base_folder)
    except Exception:
        return path


def iso_timestamp(ts: Optional[float] = None) -> str:
    """Format a UNIX timestamp (or now) into an ISO-8601 UTC string."""
    if ts is None:
        dt = datetime.utcnow()
    else:
        dt = datetime.utcfromtimestamp(ts)
    return dt.replace(microsecond=0).isoformat() + "Z"

