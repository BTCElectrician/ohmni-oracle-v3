"""Fact document generation from schedule blocks."""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, Optional

try:  # Lazy import so tests still run without OpenAI configured
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency at runtime
    OpenAI = None  # type: ignore

try:
    from .parsers import (
        build_summary,
        classify_schedule_block,
        extract_attributes,
        extract_key,
    )
except ImportError:  # When executed as a script
    from parsers import (  # type: ignore
        build_summary,
        classify_schedule_block,
        extract_attributes,
        extract_key,
    )

from .fallbacks import iter_arch_rows, iter_mech_rows, iter_panel_rows, iter_plumb_rows
from .ids import make_document_id, stable_key

logger = logging.getLogger(__name__)


def _first_non_empty(*values: Any) -> Optional[Any]:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _coerce_str(value: Any) -> Optional[str]:
    if value in (None, "", []):
        return None
    return str(value).strip()


def _build_fact_doc(
    stype: str,
    row: Dict[str, Any],
    meta: Dict[str, Any],
    client: Optional[OpenAI],
) -> Optional[Dict[str, Any]]:
    """Build a fact document from a row dict."""
    # Schedule rows remain non-embedded; client retained for signature compatibility.
    del client
    key = extract_key(stype, row)
    if not key:
        return None
    attrs = extract_attributes(stype, row)
    summary = build_summary(stype, key, attrs)
    labels = attrs.pop("_labels", [])

    panel_name = _first_non_empty(
        row.get("panel"),
        row.get("panel_name"),
        attrs.get("panel"),
        key.get("panel"),
    )
    circuit_number = _first_non_empty(
        row.get("circuit_number"),
        row.get("circuit"),
        key.get("circuit"),
        attrs.get("circuit"),
    )
    poles = _first_non_empty(
        row.get("poles"),
        row.get("pole"),
        row.get("phase"),
        attrs.get("phase"),
    )
    amps = _first_non_empty(
        row.get("amps"),
        row.get("amp"),
        row.get("trip"),
        attrs.get("rating_a"),
    )
    kva = _first_non_empty(row.get("kva"), attrs.get("kva"))
    description = _first_non_empty(
        row.get("description"),
        row.get("load_name"),
        attrs.get("description"),
    )
    doc_id = make_document_id(
        meta.get("tenant_id"),
        meta.get("job_number") or meta.get("project_id"),
        meta.get("sheet_number") or "sheet",
        "schedule-row",
        stable_key(stype, key),
    )
    doc = {
        "id": doc_id,
        "doc_type": "schedule_row",
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
        "schedule_type": stype,
        "key": key,
        "attributes": attrs,
        "labels": labels,
        "content": summary,
    }
    if "source_account" in meta:
        doc["source_account"] = meta["source_account"]
    if "source_container" in meta:
        doc["source_container"] = meta["source_container"]
    if "source_blob" in meta:
        doc["source_blob"] = meta["source_blob"]
    if "source_uri" in meta:
        doc["source_uri"] = meta["source_uri"]
    if "source_storage_name" in meta:
        doc["source_storage_name"] = meta["source_storage_name"]
    if "bbox_norm" in row:
        doc["source_bbox"] = row["bbox_norm"]
    kva_text: Optional[str]
    if isinstance(kva, (int, float)):
        kva_text = f"{kva}"
    else:
        kva_text = _coerce_str(kva)

    derived_fields = {
        "panel_name": _coerce_str(panel_name),
        "circuit_number": _coerce_str(circuit_number),
        "poles": _coerce_str(poles),
        "amps": _coerce_str(amps),
        "kva": kva_text,
        "description": _coerce_str(description),
    }
    for key_name, value in derived_fields.items():
        if value not in (None, "", []):
            doc[key_name] = value
    return doc


def emit_facts(raw_json: Dict[str, Any], meta: Dict[str, Any], client: Optional[OpenAI]) -> Iterable[Dict[str, Any]]:
    """
    Generate fact documents from schedule blocks.

    Fallback: when no `blocks` exist, synthesize rows from nested discipline structures.
    """
    blocks = raw_json.get("blocks", [])
    if blocks:
        for block in blocks:
            stype = classify_schedule_block(block)
            if not stype:
                continue
            for row in block.get("rows", []):
                doc = _build_fact_doc(stype, row, meta, client)
                if doc:
                    yield doc
        return

    # Fallback path: try discipline-specific iterators
    try:
        any_emitted = False

        # Electrical: panels → 'panel'
        for row in iter_panel_rows(raw_json):
            doc = _build_fact_doc("panel", row, meta, client)
            if doc:
                any_emitted = True
                yield doc

        # Mechanical: equipment → 'mech_equipment'
        for row in iter_mech_rows(raw_json):
            doc = _build_fact_doc("mech_equipment", row, meta, client)
            if doc:
                any_emitted = True
                yield doc

        # Plumbing: fixtures/heaters → 'plumb_equipment'
        for row in iter_plumb_rows(raw_json):
            doc = _build_fact_doc("plumb_equipment", row, meta, client)
            if doc:
                any_emitted = True
                yield doc

        # Architectural: wall/door/ceiling/finish
        for stype, row in iter_arch_rows(raw_json):
            doc = _build_fact_doc(stype, row, meta, client)
            if doc:
                any_emitted = True
                yield doc

        if not any_emitted:
            logger.debug("emit_facts: no blocks and no fallback rows found.")
    except Exception as exc:
        logger.exception("emit_facts fallback failed: %s", exc)
        return

