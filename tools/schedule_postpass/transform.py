#!/usr/bin/env python3
"""Post-process extracted schedule JSON into Azure Search docs."""
from __future__ import annotations

import argparse
import csv
import json
import logging
import pathlib
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set

try:  # Lazy import so tests still run without OpenAI configured
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency at runtime
    OpenAI = None  # type: ignore

try:
    from .parsers import (
        build_summary,
        build_template_summary,
        classify_schedule_block,
        derive_template_tags,
        extract_attributes,
        extract_key,
    )
except ImportError:  # When executed as a script
    from parsers import (  # type: ignore
        build_summary,
        build_template_summary,
        classify_schedule_block,
        derive_template_tags,
        extract_attributes,
        extract_key,
    )

PROJECT_ID_DEFAULT = "veridian"
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_KEY_SANITIZE_REGEX = re.compile(r"[^A-Za-z0-9_\-=]")


def sanitize_key_component(value: Any, fallback: str = "none") -> str:
    text = str(value or "").strip()
    if not text:
        text = fallback
    sanitized = _KEY_SANITIZE_REGEX.sub("-", text)
    sanitized = re.sub("-+", "-", sanitized)
    sanitized = sanitized.strip("-")
    return sanitized or fallback


def make_document_id(*parts: Any) -> str:
    components = [sanitize_key_component(part) for part in parts if str(part or "").strip()]
    if not components:
        return "doc"
    return "-".join(components)

def generate_embedding(text: str, client: Optional[OpenAI]) -> Optional[List[float]]:
    """Generate a vector embedding for hybrid search (best-effort)."""
    if not client:
        return None
    trimmed = (text or "").strip()
    if not trimmed:
        return None
    try:
        resp = client.embeddings.create(model="text-embedding-3-large", input=trimmed)
    except Exception as exc:  # pragma: no cover - depends on API availability
        logger.warning("Embedding generation failed (skipping vector): %s", exc)
        return None
    return resp.data[0].embedding


def load_json(path: pathlib.Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _to_iso_date(value: Any) -> str:
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
        "content": meta["content"],
        "raw_json": raw_json,
    }
    embedding = generate_embedding(doc.get("content", ""), client)
    if embedding:
        doc["content_vector"] = embedding
    return doc


def leftpad_circuit(value: Any) -> str:
    try:
        return f"{int(str(value).strip()):03d}"
    except Exception:
        return str(value)


def stable_key(schedule_type: str, key_obj: Dict[str, Any]) -> str:
    parts = [schedule_type]
    for name in sorted(key_obj.keys()):
        val = key_obj[name]
        if name == "circuit":
            val = leftpad_circuit(val)
        parts.append(f"{name}-{val}")
    return "_".join(parts)


def emit_facts(raw_json: Dict[str, Any], meta: Dict[str, Any], client: Optional[OpenAI]) -> Iterable[Dict[str, Any]]:
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


def _guess_template_type(path: pathlib.Path) -> str:
    lowered = [part.lower() for part in path.parts]
    name = path.name.lower()
    if any("architect" in part for part in lowered) or name.startswith("a_"):
        return "architectural"
    if any("elect" in part for part in lowered) or name.startswith("e_"):
        return "electrical"
    return "electrical"


def iter_template_docs(
    template_root: pathlib.Path,
    base_meta: Dict[str, Any],
    client: Optional[OpenAI],
    sheet_filter: Optional[str] = None,
) -> Iterable[Dict[str, Any]]:
    for path in sorted(template_root.rglob("*.json")):
        if sheet_filter and sheet_filter not in path.name:
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            print(f"Skipping malformed template {path}: {exc}", file=sys.stderr)
            continue

        # If this is an aggregated details file, emit one doc per room
        rooms_list = raw.get("rooms")
        if isinstance(rooms_list, list) and rooms_list:
            meta_obj = raw.get("metadata") or {}
            # Prefer explicit metadata for sheet number; fall back to filename
            agg_sheet_number = (
                raw.get("sheet_number")
                or meta_obj.get("sheet_number")
                or meta_obj.get("drawing_number")
                or path.parent.name
            )
            template_type_agg = raw.get("template_type") or _guess_template_type(path)
            # Top-level project attributes
            project_top = (
                raw.get("project_name")
                or raw.get("project")
                or meta_obj.get("project_name")
                or base_meta.get("project")
                or "Unnamed Project"
            )
            project_id_top = raw.get("project_id") or base_meta.get("project_id") or PROJECT_ID_DEFAULT
            revision_top = raw.get("revision") or meta_obj.get("revision") or base_meta.get("revision") or "IFC"
            revision_date_top = _to_iso_date(
                raw.get("revision_date") or meta_obj.get("date") or base_meta.get("revision_date")
            )
            for room in rooms_list:
                room_id = room.get("room_id") or room.get("room_number") or path.stem
                if not agg_sheet_number or not room_id:
                    print(f"Skipping room in {path}: Missing sheet_number or room_id.", file=sys.stderr)
                    continue

                tenant_id = room.get("tenant_id") or raw.get("tenant_id") or base_meta.get("tenant_id") or "ohmni"
                project = room.get("project_name") or project_top
                project_id = room.get("project_id") or project_id_top
                template_type = room.get("template_type") or template_type_agg
                summary = build_template_summary(template_type, room)
                last_mod = (
                    room.get("template_last_modified")
                    or room.get("last_modified")
                    or raw.get("template_last_modified")
                    or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                )
                levels = room.get("levels") or base_meta.get("levels") or []

                doc = {
                    "id": make_document_id(project_id, agg_sheet_number, room_id, f"template-{template_type}"),
                    "doc_type": "template",
                    "tenant_id": tenant_id,
                    "project": project,
                    "project_id": project_id,
                    "sheet_number": agg_sheet_number,
                    "room_id": room_id,
                    "room_name": room.get("room_name", ""),
                    "discipline": room.get("discipline") or ("electrical" if template_type == "electrical" else "architectural"),
                    "levels": levels,
                    "revision": room.get("revision") or revision_top,
                    "revision_date": _to_iso_date(room.get("revision_date") or revision_date_top),
                    "template_type": template_type,
                    "template_id": room.get("template_id") or f"{agg_sheet_number}-{room_id}-{template_type}",
                    "template_status": room.get("template_status", "in_progress"),
                    "template_author": room.get("template_author") or raw.get("template_author"),
                    "template_last_modified": last_mod,
                    "template_tags": sorted(set((room.get("template_tags") or []) + derive_template_tags(room))),
                    "content": summary,
                    "template_payload": json.dumps(room, ensure_ascii=False),
                }

                # Populate new room template fields from room JSON
                # A-templates: metrics, envelope, access
                metrics = room.get("metrics") or {}
                if isinstance(metrics, dict):
                    doc["metrics_dimensions"] = str(metrics.get("dimensions") or "")[:512]
                    sf = metrics.get("square_footage")
                    if isinstance(sf, (int, float)):
                        doc["square_footage"] = float(sf)
                    elif isinstance(sf, str) and sf.strip():
                        try:
                            doc["square_footage"] = float(sf.strip())
                        except (ValueError, TypeError):
                            pass
                    doc["ceiling_height"] = str(metrics.get("ceiling_height") or "")[:128]

                envelope = room.get("envelope") or {}
                if isinstance(envelope, dict):
                    doc["ceiling_type"] = str(envelope.get("ceiling_type") or "")[:128]
                    walls = envelope.get("walls") or []
                    if isinstance(walls, list):
                        doc["walls"] = [str(w) for w in walls if isinstance(w, (str, int, float))][:100]

                access = room.get("access") or {}
                if isinstance(access, dict):
                    doors = access.get("doors") or []
                    if isinstance(doors, list):
                        doc["doors"] = [str(d) for d in doors if isinstance(d, (str, int, float))][:100]
                        doc["doors_count"] = len(doc["doors"])

                # E-templates: systems
                systems = room.get("systems") or {}
                if isinstance(systems, dict):
                    def _normalize_list(x):
                        if not isinstance(x, list):
                            return []
                        return [str(s) for s in x if isinstance(s, (str, int, float))][:100]
                    
                    doc["systems_power"] = _normalize_list(systems.get("power"))
                    doc["systems_lighting"] = _normalize_list(systems.get("lighting"))
                    doc["systems_emergency"] = _normalize_list(systems.get("emergency"))
                    doc["systems_fire_alarm"] = _normalize_list(systems.get("fire_alarm"))
                    doc["systems_low_voltage"] = _normalize_list(systems.get("low_voltage"))
                    doc["systems_mechanical"] = _normalize_list(systems.get("mechanical"))
                    doc["systems_special"] = _normalize_list(systems.get("special"))

                    # Derive counts and token lists from systems
                    doc["fixtures_count"] = len(doc["systems_lighting"])
                    doc["fixture_types"] = list(set(doc["systems_lighting"]))
                    
                    # Heuristic: count outlets and circuits from power systems strings
                    power_strs = doc["systems_power"]
                    doc["outlets_count"] = sum(1 for s in power_strs if "outlet" in str(s).lower())
                    doc["outlet_types"] = list(set([s for s in power_strs if "outlet" in str(s).lower()]))
                    doc["circuits_count"] = sum(1 for s in power_strs if "circuit" in str(s).lower() or "ckt" in str(s).lower())
                    doc["circuits"] = list(set([s for s in power_strs if "circuit" in str(s).lower() or "ckt" in str(s).lower()]))

                # Notes
                notes = room.get("notes") or {}
                if isinstance(notes, dict):
                    doc["notes_field"] = str(notes.get("field") or "")[:2048]
                    photos = notes.get("photos") or []
                    if isinstance(photos, list):
                        doc["notes_photo_urls"] = [str(p) for p in photos if isinstance(p, (str, int, float))][:50]

                # Source linkage (best-effort from aggregate metadata)
                source_doc = raw.get("source_document") or {}
                if isinstance(source_doc, dict):
                    doc["source_pdf_blob_path"] = str(source_doc.get("storage_name") or source_doc.get("uri") or base_meta.get("source_file") or "")[:512]
                    doc["source_pdf_etag"] = str(source_doc.get("etag") or "")[:128]
                structured_path = room.get("source_structured_json_path") or base_meta.get("source_file", "").replace("_structured.json", "") + "_structured.json"
                doc["source_structured_json_path"] = str(structured_path)[:512]
                doc["source_template_json_path"] = str(path)[:512]

                # Enhance content summary to include salient fields for vector search
                summary_parts = [summary]
                if doc.get("square_footage"):
                    summary_parts.append(f"sf {doc['square_footage']}")
                if doc.get("ceiling_type"):
                    summary_parts.append(doc["ceiling_type"])
                if doc.get("systems_power"):
                    summary_parts.extend(doc["systems_power"][:5])
                if doc.get("systems_lighting"):
                    summary_parts.extend(doc["systems_lighting"][:5])
                if doc.get("systems_emergency"):
                    summary_parts.extend(doc["systems_emergency"][:3])
                if doc.get("notes_field"):
                    summary_parts.append(doc["notes_field"][:200])
                enhanced_content = " | ".join([p for p in summary_parts if p])
                doc["content"] = enhanced_content

                embedding = generate_embedding(enhanced_content, client)
                if embedding:
                    doc["content_vector"] = embedding
                yield doc
            continue

        # Otherwise, treat as single-room template JSON and emit one doc
        template_type = raw.get("template_type") or _guess_template_type(path)
        sheet_number = raw.get("sheet_number") or path.parent.name
        room_id = raw.get("room_id") or path.stem
        if not sheet_number or not room_id:
            print(f"Skipping template {path}: Missing sheet_number or room_id.", file=sys.stderr)
            continue

        summary = build_template_summary(template_type, raw)
        revision = raw.get("revision") or base_meta.get("revision") or "IFC"
        revision_date = _to_iso_date(
            raw.get("revision_date") or base_meta.get("revision_date")
        )
        last_mod = (
            raw.get("template_last_modified")
            or raw.get("last_modified")
            or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

        project = (
            raw.get("project_name")
            or raw.get("project")
            or base_meta.get("project")
            or "Unnamed Project"
        )
        project_id = raw.get("project_id") or base_meta.get("project_id") or PROJECT_ID_DEFAULT
        tenant_id = raw.get("tenant_id") or base_meta.get("tenant_id") or "ohmni"

        doc = {
            "id": make_document_id(project_id, sheet_number, room_id, f"template-{template_type}"),
            "doc_type": "template",
            "tenant_id": tenant_id,
            "project": project,
            "project_id": project_id,
            "sheet_number": sheet_number,
            "room_id": room_id,
            "room_name": raw.get("room_name", ""),
            "discipline": raw.get("discipline") or ("electrical" if template_type == "electrical" else "architectural"),
            "levels": raw.get("levels") or base_meta.get("levels") or [],
            "revision": revision,
            "revision_date": revision_date,
            "template_type": template_type,
            "template_id": raw.get("template_id") or f"{sheet_number}-{room_id}-{template_type}",
            "template_status": raw.get("template_status", "in_progress"),
            "template_author": raw.get("template_author"),
            "template_last_modified": last_mod,
            "template_tags": sorted(set((raw.get("template_tags") or []) + derive_template_tags(raw))),
            "content": summary,
            "template_payload": json.dumps(raw, ensure_ascii=False),
        }

        # Populate new room template fields from raw template JSON
        # A-templates: metrics, envelope, access
        metrics = raw.get("metrics") or {}
        if isinstance(metrics, dict):
            doc["metrics_dimensions"] = str(metrics.get("dimensions") or "")[:512]
            sf = metrics.get("square_footage")
            if isinstance(sf, (int, float)):
                doc["square_footage"] = float(sf)
            elif isinstance(sf, str) and sf.strip():
                try:
                    doc["square_footage"] = float(sf.strip())
                except (ValueError, TypeError):
                    pass
            doc["ceiling_height"] = str(metrics.get("ceiling_height") or "")[:128]

        envelope = raw.get("envelope") or {}
        if isinstance(envelope, dict):
            doc["ceiling_type"] = str(envelope.get("ceiling_type") or "")[:128]
            walls = envelope.get("walls") or []
            if isinstance(walls, list):
                doc["walls"] = [str(w) for w in walls if isinstance(w, (str, int, float))][:100]

        access = raw.get("access") or {}
        if isinstance(access, dict):
            doors = access.get("doors") or []
            if isinstance(doors, list):
                doc["doors"] = [str(d) for d in doors if isinstance(d, (str, int, float))][:100]
                doc["doors_count"] = len(doc["doors"])

        # E-templates: systems
        systems = raw.get("systems") or {}
        if isinstance(systems, dict):
            def _normalize_list(x):
                if not isinstance(x, list):
                    return []
                return [str(s) for s in x if isinstance(s, (str, int, float))][:100]
            
            doc["systems_power"] = _normalize_list(systems.get("power"))
            doc["systems_lighting"] = _normalize_list(systems.get("lighting"))
            doc["systems_emergency"] = _normalize_list(systems.get("emergency"))
            doc["systems_fire_alarm"] = _normalize_list(systems.get("fire_alarm"))
            doc["systems_low_voltage"] = _normalize_list(systems.get("low_voltage"))
            doc["systems_mechanical"] = _normalize_list(systems.get("mechanical"))
            doc["systems_special"] = _normalize_list(systems.get("special"))

            # Derive counts and token lists from systems
            doc["fixtures_count"] = len(doc["systems_lighting"])
            doc["fixture_types"] = list(set(doc["systems_lighting"]))
            
            # Heuristic: count outlets and circuits from power systems strings
            power_strs = doc["systems_power"]
            doc["outlets_count"] = sum(1 for s in power_strs if "outlet" in str(s).lower())
            doc["outlet_types"] = list(set([s for s in power_strs if "outlet" in str(s).lower()]))
            doc["circuits_count"] = sum(1 for s in power_strs if "circuit" in str(s).lower() or "ckt" in str(s).lower())
            doc["circuits"] = list(set([s for s in power_strs if "circuit" in str(s).lower() or "ckt" in str(s).lower()]))

        # Notes
        notes = raw.get("notes") or {}
        if isinstance(notes, dict):
            doc["notes_field"] = str(notes.get("field") or "")[:2048]
            photos = notes.get("photos") or []
            if isinstance(photos, list):
                doc["notes_photo_urls"] = [str(p) for p in photos if isinstance(p, (str, int, float))][:50]

        # Source linkage
        source_doc = raw.get("source_document") or {}
        if isinstance(source_doc, dict):
            doc["source_pdf_blob_path"] = str(source_doc.get("storage_name") or source_doc.get("uri") or base_meta.get("source_file") or "")[:512]
            doc["source_pdf_etag"] = str(source_doc.get("etag") or "")[:128]
        
        # Get structured JSON path from base_meta or raw
        structured_path = raw.get("source_structured_json_path") or base_meta.get("source_file", "").replace("_structured.json", "") + "_structured.json"
        doc["source_structured_json_path"] = str(structured_path)[:512]
        doc["source_template_json_path"] = str(path)[:512]

        # Enhance content summary to include new fields for better vector search
        summary_parts = [summary]
        if doc.get("square_footage"):
            summary_parts.append(f"sf {doc['square_footage']}")
        if doc.get("ceiling_type"):
            summary_parts.append(doc["ceiling_type"])
        if doc.get("systems_power"):
            summary_parts.extend(doc["systems_power"][:5])
        if doc.get("systems_lighting"):
            summary_parts.extend(doc["systems_lighting"][:5])
        if doc.get("systems_emergency"):
            summary_parts.extend(doc["systems_emergency"][:3])
        if doc.get("notes_field"):
            summary_parts.append(doc["notes_field"][:200])
        
        enhanced_content = " | ".join([p for p in summary_parts if p])
        doc["content"] = enhanced_content

        embedding = generate_embedding(enhanced_content, client)
        if embedding:
            doc["content_vector"] = embedding
        yield doc


def write_jsonl(path: pathlib.Path, docs: Iterable[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for doc in docs:
            doc.pop("raw_json", None)
            handle.write(json.dumps(doc, ensure_ascii=False) + "\n")


def coverage_rows(
    sheet_doc: Dict[str, Any],
    facts: List[Dict[str, Any]],
    templates: List[Dict[str, Any]],
) -> List[List[str]]:
    bucket: Dict[str, List[Dict[str, Any]]] = {}
    for fact in facts:
        bucket.setdefault(fact["schedule_type"], []).append(fact)

    rows: List[List[str]] = []
    sheet_number = sheet_doc.get("sheet_number") or "<unknown>"

    for stype, items in bucket.items():
        total = len(items)
        with_keys = sum(1 for item in items if item.get("key"))
        with_panel_circuit = sum(
            1
            for item in items
            if (item.get("key") or {}).get("panel") and (item.get("key") or {}).get("circuit")
        )
        with_voltage = sum(1 for item in items if (item.get("attributes") or {}).get("voltage") is not None)
        with_mca_mop = sum(
            1
            for item in items
            if (item.get("attributes") or {}).get("mca") is not None
            and (item.get("attributes") or {}).get("mop") is not None
        )
        rows.append(
            [
                sheet_number,
                stype,
                str(total),
                str(with_keys),
                str(with_panel_circuit),
                str(with_voltage),
                str(with_mca_mop),
                "",
                "",
                "",
            ]
        )

    if templates:
        total_templates = len(templates)
        last_mod = max((t.get("template_last_modified") for t in templates), default="N/A")
        signed_off = sum(1 for t in templates if t.get("template_status") == "signed_off")
        pct = f"{(signed_off / total_templates) * 100:.1f}%" if total_templates else "0%"
        rows.append(
            [
                sheet_number,
                "template",
                str(total_templates),
                "",
                "",
                "",
                "",
                last_mod,
                str(signed_off),
                pct,
            ]
        )

    return rows


def _collect_sheet_templates(
    template_root: pathlib.Path,
    drawing_slug: Optional[str],
    sheet_number: Optional[str],
    meta: Dict[str, Any],
    client: Optional[OpenAI],
) -> List[Dict[str, Any]]:
    if not sheet_number:
        return []

    candidates: Set[pathlib.Path] = set()

    if drawing_slug:
        slug_dir = template_root / drawing_slug
        if slug_dir.exists():
            candidates.add(slug_dir)

    for discipline in ("electrical", "architectural"):
        legacy_dir = template_root / discipline / sheet_number
        if legacy_dir.exists():
            candidates.add(legacy_dir)

    if not candidates:
        # Fall back to a wildcard search for filenames containing the sheet number
        for path in template_root.rglob(f"*{sheet_number}*"):
            if path.is_dir():
                candidates.add(path)
            elif path.is_file():
                # Use parent so iter_template_docs can rglob beneath it
                candidates.add(path.parent)

    results: List[Dict[str, Any]] = []
    for root in sorted(candidates):
        results.extend(
            list(
                iter_template_docs(
                    root,
                    meta,
                    client,
                    sheet_filter=sheet_number,
                )
            )
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_json_folder", help="path to sheet JSON folder (output of OCR)")
    parser.add_argument("output_folder", help="path to output folder (JSONL target)")
    parser.add_argument("project_id", nargs="?", default=PROJECT_ID_DEFAULT, help="project identifier")
    parser.add_argument(
        "--templates-root",
        required=True,
        type=pathlib.Path,
        help="root folder containing filled-in room templates",
    )
    parser.add_argument(
        "--templates-only",
        action="store_true",
        help="skip sheet/fact parsing and only regenerate template docs",
    )
    args = parser.parse_args()

    input_dir = pathlib.Path(args.input_json_folder)
    output_dir = pathlib.Path(args.output_folder)
    template_root = args.templates_root
    project_id = args.project_id

    if not template_root.exists():
        raise FileNotFoundError(f"Template root not found: {template_root}")

    try:
        embedding_client = OpenAI() if OpenAI else None
    except Exception as exc:  # pragma: no cover - depends on env
        print(f"Warning: Unable to initialize OpenAI client ({exc}). Embeddings disabled.", file=sys.stderr)
        embedding_client = None

    output_dir.mkdir(parents=True, exist_ok=True)
    sheets_jsonl = output_dir / "sheets.jsonl"
    facts_jsonl = output_dir / "facts.jsonl"
    templates_jsonl = output_dir / "templates.jsonl"
    coverage_csv = output_dir / "coverage_report.csv"

    all_sheets: List[Dict[str, Any]] = []
    all_facts: List[Dict[str, Any]] = []
    all_templates: List[Dict[str, Any]] = []

    coverage_header = [
        "sheet_number",
        "schedule_type",
        "rows_total",
        "rows_with_key_id",
        "rows_with_panel_and_circuit",
        "rows_with_voltage",
        "rows_with_mca_mop",
        "template_last_modified",
        "templates_signed_off",
        "templates_signed_off_pct",
    ]
    coverage_rows_data: List[List[str]] = [coverage_header]

    if not args.templates_only:
        print("Processing sheets and facts...")
        for json_path in sorted(input_dir.rglob("*_structured.json")):
            raw = load_json(json_path)
            meta = sheet_meta(raw, project_id)
            sheet_doc = make_sheet_doc(meta, raw, embedding_client)
            facts = list(emit_facts(raw, meta, embedding_client))
            drawing_slug = json_path.parent.name
            templates_for_sheet = _collect_sheet_templates(
                template_root,
                drawing_slug,
                meta.get("sheet_number"),
                meta,
                embedding_client,
            )

            all_sheets.append(sheet_doc)
            all_facts.extend(facts)
            all_templates.extend(templates_for_sheet)
            coverage_rows_data.extend(coverage_rows(sheet_doc, facts, templates_for_sheet))

        write_jsonl(sheets_jsonl, all_sheets)
        write_jsonl(facts_jsonl, all_facts)
        print(f"Wrote {len(all_sheets)} sheets -> {sheets_jsonl}")
        print(f"Wrote {len(all_facts)} facts  -> {facts_jsonl}")
    else:
        print("Skipping sheet and fact processing (--templates-only set).")
        base_meta = sheet_meta({}, project_id)
        all_templates = list(iter_template_docs(template_root, base_meta, embedding_client))
        if all_templates:
            bucket: Dict[str, List[Dict[str, Any]]] = {}
            for template in all_templates:
                bucket.setdefault(template["sheet_number"], []).append(template)
            for sheet_number, templates in bucket.items():
                coverage_rows_data.extend(
                    coverage_rows({"sheet_number": sheet_number}, [], templates)
                )

    if not args.templates_only:
        print("Processing templates...")
    write_jsonl(templates_jsonl, all_templates)
    print(f"Wrote {len(all_templates)} templates -> {templates_jsonl}")

    with coverage_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerows(coverage_rows_data)
    print(f"Wrote coverage           -> {coverage_csv}")


if __name__ == "__main__":
    main()
