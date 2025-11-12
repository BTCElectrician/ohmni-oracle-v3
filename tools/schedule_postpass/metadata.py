"""Sheet metadata extraction and document creation."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:  # Lazy import so tests still run without OpenAI configured
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency at runtime
    OpenAI = None  # type: ignore

from .embeddings import generate_embedding
from .ids import make_document_id


def _to_iso_date(value: Any) -> str:
    """Convert various date formats to ISO 8601 UTC string."""
    if not value:
        return "2000-01-01T00:00:00Z"
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return "2000-01-01T00:00:00Z"
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            pass
        for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(text, fmt)
                return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
            except ValueError:
                continue
    if isinstance(value, (int, float)):
        try:
            dt = datetime.fromtimestamp(value, tz=timezone.utc)
            return dt.isoformat().replace("+00:00", "Z")
        except Exception:
            pass
    return "2000-01-01T00:00:00Z"


def sheet_meta(raw: Dict[str, Any], project_id: str) -> Dict[str, Any]:
    """Extract sheet metadata from raw JSON."""
    drawing_meta = raw.get("DRAWING_METADATA") or {}
    sheet_number = (
        raw.get("sheet_number")
        or drawing_meta.get("sheet_number")
        or drawing_meta.get("drawing_number")
        or raw.get("drawing_number")
        or "sheet"
    )
    sheet_title = (
        raw.get("sheet_title")
        or drawing_meta.get("title")
        or raw.get("title")
        or ""
    )
    discipline = (
        (raw.get("discipline") or drawing_meta.get("discipline") or "").lower()
        or "architectural"
    )
    revision = (
        raw.get("revision")
        or drawing_meta.get("revision")
        or "IFC"
    )
    revision_date = _to_iso_date(
        raw.get("revision_date")
        or drawing_meta.get("revision_date")
        or drawing_meta.get("date")
    )
    levels = raw.get("levels") or drawing_meta.get("levels") or []
    content = raw.get("content", "")
    source_file = (
        raw.get("source_file")
        or drawing_meta.get("source_file")
        or "<blob/path>.pdf"
    )

    return {
        "tenant_id": raw.get("tenant_id") or "ohmni",
        "project": raw.get("project_name") or raw.get("project") or project_id or "Unnamed Project",
        "project_id": project_id,
        "sheet_number": sheet_number,
        "sheet_title": sheet_title,
        "discipline": discipline,
        "revision": revision,
        "revision_date": revision_date,
        "levels": levels,
        "source_file": source_file,
        "content": content,
    }


def make_sheet_doc(meta: Dict[str, Any], raw_json: Dict[str, Any], client: Optional[OpenAI]) -> Dict[str, Any]:
    """Create a sheet document for Azure Search."""
    structured_payload = json.dumps(raw_json, ensure_ascii=False)
    header_parts = [
        f"Sheet {meta.get('sheet_number')}: {meta.get('sheet_title')}".strip(),
        f"Discipline: {meta.get('discipline')}".strip(),
        f"Revision: {meta.get('revision')} ({meta.get('revision_date')})".strip(),
    ]
    header_text = " | ".join([part for part in header_parts if part])
    combined_content = "\n".join(filter(None, [header_text, structured_payload]))
    doc_id = make_document_id(meta.get("project_id"), meta.get("sheet_number") or "sheet", meta.get("revision") or "rev")
    doc = {
        "id": doc_id,
        "doc_type": "sheet",
        "tenant_id": meta.get("tenant_id", "ohmni"),
        "project": meta["project"],
        "project_id": meta["project_id"],
        "sheet_number": meta["sheet_number"],
        "sheet_title": meta["sheet_title"],
        "discipline": meta["discipline"],
        "revision": meta["revision"],
        "revision_date": meta["revision_date"],
        "levels": meta["levels"],
        "source_file": meta["source_file"],
        "content": combined_content,
        "sheet_payload": structured_payload,
    }
    embedding = generate_embedding(doc.get("content", ""), client)
    if embedding:
        doc["content_vector"] = embedding
    return doc

