"""Fact document generation from schedule blocks."""
from __future__ import annotations

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
from .ids import make_document_id, stable_key


def emit_facts(raw_json: Dict[str, Any], meta: Dict[str, Any], client: Optional[OpenAI]) -> Iterable[Dict[str, Any]]:
    """Generate fact documents from schedule blocks."""
    for block in raw_json.get("blocks", []):
        stype = classify_schedule_block(block)
        if not stype:
            continue
        for row in block.get("rows", []):
            key = extract_key(stype, row)
            if not key:
                continue
            attrs = extract_attributes(stype, row)
            summary = build_summary(stype, key, attrs)
            doc = {
                "id": make_document_id(meta.get("project_id"), meta.get("sheet_number") or "sheet", meta.get("revision") or "rev", f"row-{stable_key(stype, key)}"),
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
            yield doc

