"""Sheet chunk document generation for the drawings_unified index."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:  # Optional dependency so tests pass without OpenAI configured
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency at runtime
    OpenAI = None  # type: ignore

from .embeddings import generate_embedding
from .fallbacks import iter_mech_rows, iter_panel_rows, iter_plumb_rows
from .ids import sanitize_key_component
from .parsers import build_summary, classify_schedule_block, extract_attributes, extract_key

ScheduleChunk = Tuple[str, str, Any, str]

CHUNK_SOURCES: Sequence[ScheduleChunk] = (
    ("panel_schedule", "panel", iter_panel_rows, "/ELECTRICAL/panels"),
    ("mech_schedule", "mech_equipment", iter_mech_rows, "/MECHANICAL"),
    ("plumb_schedule", "plumb_equipment", iter_plumb_rows, "/PLUMBING"),
)

MAX_ROW_LINES = 30
MAX_CONTENT_CHARS = 1500


def iter_sheet_chunks(
    raw_json: Dict[str, Any],
    meta: Dict[str, Any],
    client: Optional[OpenAI],
) -> Iterable[Dict[str, Any]]:
    """
    Yield sheet chunk documents covering panel/mechanical/plumbing schedules and notes.
    """
    chunk_idx = 1
    page_number = _infer_page(raw_json)

    for chunk_type, schedule_type, iterator, json_ptr in CHUNK_SOURCES:
        rows, pointer = _collect_schedule_rows(raw_json, schedule_type, iterator, json_ptr)
        if not rows:
            continue
        content = _summarize_schedule_chunk(meta, schedule_type, chunk_type, rows)
        if not content:
            continue
        chunk_doc = _make_chunk_doc(
            meta=meta,
            chunk_type=chunk_type,
            content=content,
            chunk_index=chunk_idx,
            page_number=page_number,
            json_ptr=pointer,
            client=client,
        )
        yield chunk_doc
        chunk_idx += 1

    notes_content = _summarize_notes(raw_json, meta)
    if notes_content:
        yield _make_chunk_doc(
            meta=meta,
            chunk_type="notes",
            content=notes_content,
            chunk_index=chunk_idx,
            page_number=page_number,
            json_ptr="/notes",
            client=client,
        )
        chunk_idx += 1

    general_content = _summarize_general(raw_json, meta)
    if general_content:
        yield _make_chunk_doc(
            meta=meta,
            chunk_type="general",
            content=general_content,
            chunk_index=chunk_idx,
            page_number=page_number,
            json_ptr="/content",
            client=client,
        )


def _infer_page(raw_json: Dict[str, Any]) -> int:
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
    return 1


def _sanitize_path_component(value: Optional[str], fallback: str) -> str:
    return sanitize_key_component(value or fallback, fallback=fallback)


def _make_chunk_id(meta: Dict[str, Any], chunk_index: int) -> str:
    tenant = _sanitize_path_component(meta.get("tenant_id"), "tenant")
    job_or_project = _sanitize_path_component(meta.get("job_number") or meta.get("project_id"), "project")
    sheet = _sanitize_path_component(meta.get("sheet_number"), "sheet")
    return f"{tenant}-{job_or_project}-{sheet}-chunk-{chunk_index:04d}"


def _make_chunk_doc(
    meta: Dict[str, Any],
    chunk_type: str,
    content: str,
    chunk_index: int,
    page_number: int,
    json_ptr: str,
    client: Optional[OpenAI],
) -> Dict[str, Any]:
    doc: Dict[str, Any] = {
        "id": _make_chunk_id(meta, chunk_index),
        "doc_type": "sheet_chunk",
        "tenant_id": meta.get("tenant_id", "ohmni"),
        "project": meta.get("project"),
        "project_id": meta.get("project_id"),
        "job_number": meta.get("job_number"),
        "sheet_number": meta.get("sheet_number"),
        "sheet_title": meta.get("sheet_title"),
        "discipline": meta.get("discipline"),
        "revision": meta.get("revision"),
        "revision_date": meta.get("revision_date"),
        "levels": meta.get("levels"),
        "source_file": meta.get("source_file"),
        "chunk_type": chunk_type,
        "page": page_number,
        "content": content,
    }
    for key in ("source_account", "source_container", "source_blob", "source_uri", "source_storage_name"):
        value = meta.get(key)
        if value:
            doc[key] = value
    embedding = generate_embedding(content, client)
    if embedding:
        doc["content_vector"] = embedding
    if json_ptr:
        doc["json_ptr"] = json_ptr
    return doc


def _summarize_schedule_chunk(
    meta: Dict[str, Any],
    schedule_type: str,
    chunk_type: str,
    rows: Sequence[Dict[str, Any]],
) -> str:
    header = f"{meta.get('sheet_number')} {chunk_type.replace('_', ' ').title()} ({len(rows)} rows)"
    lines: List[str] = []
    for row in rows[:MAX_ROW_LINES]:
        key = extract_key(schedule_type, row)
        attrs = extract_attributes(schedule_type, row)
        summary = build_summary(schedule_type, key, attrs)
        if summary and summary.lower() != "row":
            lines.append(summary)
            continue
        fallback = _row_fallback_summary(row, attrs)
        if fallback:
            lines.append(fallback)
    body = "\n".join(f"- {line}" for line in lines if line)
    text = header if not body else f"{header}\n{body}"
    return _truncate_content(text)


def _collect_schedule_rows(
    raw_json: Dict[str, Any],
    schedule_type: str,
    iterator: Any,
    default_ptr: str,
) -> Tuple[List[Dict[str, Any]], str]:
    rows = list(iterator(raw_json))
    if rows:
        return rows, default_ptr

    blocks = raw_json.get("blocks")
    if not isinstance(blocks, list):
        return rows, default_ptr

    collected: List[Dict[str, Any]] = []
    pointer = default_ptr
    for idx, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue
        if classify_schedule_block(block) != schedule_type:
            continue
        pointer = f"/blocks/{idx}"
        for row in block.get("rows", []) or []:
            if isinstance(row, dict):
                collected.append(row)
        if collected:
            break

    if collected:
        return collected, pointer
    return rows, default_ptr


def _row_fallback_summary(row: Dict[str, Any], attrs: Dict[str, Any]) -> str:
    important_keys = (
        "panel",
        "panel_name",
        "circuit",
        "circuit_number",
        "tag",
        "description",
        "amps",
        "trip",
        "voltage",
        "kva",
    )
    parts: List[str] = []
    for key in important_keys:
        value = row.get(key)
        if value in (None, "", []):
            value = attrs.get(key)
        if value in (None, "", []):
            continue
        parts.append(f"{key}={value}")
    return ", ".join(parts)


def _summarize_notes(raw_json: Dict[str, Any], meta: Dict[str, Any]) -> Optional[str]:
    notes = raw_json.get("notes") or raw_json.get("NOTES") or raw_json.get("general_notes")
    if not notes:
        return None

    if isinstance(notes, list):
        lines = [str(item).strip() for item in notes if item not in (None, "", [])]
        body = "\n".join(lines)
    elif isinstance(notes, dict):
        lines = []
        for key, value in notes.items():
            if value in (None, "", []):
                continue
            lines.append(f"{key}: {value}")
        body = "\n".join(lines)
    else:
        body = str(notes).strip()

    if not body:
        return None
    header = f"{meta.get('sheet_number')} notes"
    return _truncate_content(f"{header}\n{body}")


def _summarize_general(raw_json: Dict[str, Any], meta: Dict[str, Any]) -> Optional[str]:
    content = raw_json.get("content") or raw_json.get("CONTENT")
    if not isinstance(content, str):
        return None
    text = content.strip()
    if not text:
        return None
    header = f"{meta.get('sheet_number')} general context"
    return _truncate_content(f"{header}\n{text}")


def _truncate_content(text: str) -> str:
    if len(text) <= MAX_CONTENT_CHARS:
        return text
    return text[: MAX_CONTENT_CHARS - 3].rstrip() + "..."

