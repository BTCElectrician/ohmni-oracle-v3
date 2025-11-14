"""Sheet metadata extraction and document creation."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlparse

try:  # Lazy import so tests still run without OpenAI configured
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency at runtime
    OpenAI = None  # type: ignore

from .embeddings import generate_embedding
from .ids import make_document_id
from .page_utils import infer_page


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


def _coerce_str(value: Any) -> Optional[str]:
    if value in (None, "", []):
        return None
    return str(value).strip()


def _infer_discipline_from_sections(raw: Dict[str, Any]) -> Optional[str]:
    """Infer discipline from top-level discipline sections when explicit discipline is missing."""
    known_disciplines = {"ELECTRICAL", "MECHANICAL", "PLUMBING", "ARCHITECTURAL"}
    found = [key for key in known_disciplines if key in raw and isinstance(raw[key], dict)]
    if len(found) == 1:
        return found[0].lower()
    return None


def _derive_source_fields(raw: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Best-effort extraction of storage account/container/blob identifiers."""
    source_doc = raw.get("source_document") or raw.get("source_document_info")
    if not isinstance(source_doc, dict):
        return {}

    uri = _coerce_str(source_doc.get("uri"))
    storage_name = _coerce_str(source_doc.get("storage_name"))
    storage_meta = source_doc.get("storage_metadata") or {}
    if isinstance(storage_meta, dict):
        storage_name = _coerce_str(storage_meta.get("storage_name")) or storage_name

    source_account: Optional[str] = None
    source_container: Optional[str] = None
    source_blob: Optional[str] = None

    if uri:
        try:
            parsed = urlparse(uri)
            host_parts = (parsed.netloc or "").split(".")
            if host_parts:
                source_account = host_parts[0] or None
            path = (parsed.path or "").lstrip("/")
            if path:
                parts = path.split("/", 1)
                if len(parts) == 2:
                    source_container, source_blob = parts[0], parts[1]
                else:
                    source_blob = parts[0]
        except Exception:
            source_account = None

    if storage_name and not source_blob:
        parts = storage_name.split("/", 1)
        if len(parts) == 2:
            source_container = source_container or parts[0]
            source_blob = parts[1]
        else:
            source_blob = source_blob or storage_name

    payload: Dict[str, Optional[str]] = {}
    if uri:
        payload["source_uri"] = uri
    if storage_name:
        payload["source_storage_name"] = storage_name
    if source_account:
        payload["source_account"] = source_account
    if source_container:
        payload["source_container"] = source_container
    if source_blob:
        payload["source_blob"] = source_blob
    return payload


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
    explicit_discipline = (raw.get("discipline") or drawing_meta.get("discipline") or "").strip().lower()
    if explicit_discipline:
        discipline = explicit_discipline
    else:
        inferred = _infer_discipline_from_sections(raw)
        discipline = inferred or "architectural"
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

    job_number = (
        raw.get("job_number")
        or raw.get("job_no")
        or drawing_meta.get("job_number")
        or drawing_meta.get("job_no")
    )

    meta = {
        "tenant_id": raw.get("tenant_id") or "ohmni",
        "project": raw.get("project_name") or raw.get("project") or project_id or "Unnamed Project",
        "project_id": project_id,
        "job_number": _coerce_str(job_number),
        "sheet_number": sheet_number,
        "sheet_title": sheet_title,
        "discipline": discipline,
        "revision": revision,
        "revision_date": revision_date,
        "levels": levels,
        "source_file": source_file,
        "content": content,
        "page": infer_page(raw),
    }
    meta.update(_derive_source_fields(raw))
    return meta


def make_sheet_doc(meta: Dict[str, Any], raw_json: Dict[str, Any], client: Optional[OpenAI]) -> Dict[str, Any]:
    """Create a sheet document for Azure Search."""
    structured_payload = json.dumps(raw_json, ensure_ascii=False)
    header_parts = [
        f"Sheet {meta.get('sheet_number')}: {meta.get('sheet_title')}".strip(),
        f"Discipline: {meta.get('discipline')}".strip(),
        f"Revision: {meta.get('revision')} ({meta.get('revision_date')})".strip(),
    ]
    header_text = " | ".join([part for part in header_parts if part])
    # Keep searchable content small; full JSON remains in 'sheet_payload'
    combined_content = header_text
    doc_id = make_document_id(meta.get("project_id"), meta.get("sheet_number") or "sheet", meta.get("revision") or "rev")
    doc = {
        "id": doc_id,
        "doc_type": "sheet",
        "tenant_id": meta.get("tenant_id", "ohmni"),
        "project": meta["project"],
        "project_id": meta["project_id"],
        "job_number": meta.get("job_number"),
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
    for key in ("source_account", "source_container", "source_blob", "source_uri", "source_storage_name"):
        value = meta.get(key)
        if value:
            doc[key] = value
    # No embeddings for full sheet docs; vectors live on 'sheet_chunk' docs
    return doc

