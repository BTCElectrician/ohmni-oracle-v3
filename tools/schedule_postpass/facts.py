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

from .embeddings import generate_embedding
from .fallbacks import iter_arch_rows, iter_mech_rows, iter_panel_rows, iter_plumb_rows
from .ids import make_document_id, stable_key

logger = logging.getLogger(__name__)


def _build_fact_doc(
    stype: str,
    row: Dict[str, Any],
    meta: Dict[str, Any],
    client: Optional[OpenAI],
) -> Optional[Dict[str, Any]]:
    """Build a fact document from a row dict."""
    key = extract_key(stype, row)
    if not key:
        return None
    attrs = extract_attributes(stype, row)
    summary = build_summary(stype, key, attrs)
    doc = {
        "id": make_document_id(
            meta.get("project_id"),
            meta.get("sheet_number") or "sheet",
            meta.get("revision") or "rev",
            f"row-{stable_key(stype, key)}",
        ),
        "doc_type": "fact",
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
        "schedule_type": stype,
        "key": key,
        "attributes": attrs,
        "labels": attrs.pop("_labels", []),
        "content": summary,
    }
    if "bbox_norm" in row:
        doc["source_bbox"] = row["bbox_norm"]
    embedding = generate_embedding(summary, client)
    if embedding:
        doc["content_vector"] = embedding
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

