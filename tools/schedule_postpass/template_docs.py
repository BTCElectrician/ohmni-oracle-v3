"""Template document generation from room templates."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set

import pathlib

try:  # Lazy import so tests still run without OpenAI configured
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency at runtime
    OpenAI = None  # type: ignore

try:
    from .parsers import (
        build_template_summary,
        derive_template_tags,
    )
except ImportError:  # When executed as a script
    from parsers import (  # type: ignore
        build_template_summary,
        derive_template_tags,
    )

from .embeddings import generate_embedding
from .ids import _is_bogus_room, make_document_id
from .metadata import _to_iso_date

PROJECT_ID_DEFAULT = "veridian"


def _guess_template_type(path: pathlib.Path) -> str:
    """Guess template type from file path."""
    full_lower = str(path).lower()
    lowered = [part.lower() for part in path.parts]
    name = path.name.lower()
    if "_a_rooms" in full_lower or "-a_rooms" in full_lower or any("architect" in part for part in lowered) or name.startswith("a_"):
        return "architectural"
    if "_e_rooms" in full_lower or "-e_rooms" in full_lower or any("elect" in part for part in lowered) or name.startswith("e_"):
        return "electrical"
    return "electrical"


def iter_template_docs(
    template_root: pathlib.Path,
    base_meta: Dict[str, Any],
    client: Optional[OpenAI],
    sheet_filter: Optional[str] = None,
) -> Iterable[Dict[str, Any]]:
    """Generate template documents from JSON template files."""
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
                if _is_bogus_room(room):
                    print(f"Skipping bogus room in {path}: {room.get('room_name') or room.get('room_number') or room_id}", file=sys.stderr)
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
                    "doc_type": "room",
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
            "doc_type": "room",
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


def _collect_sheet_templates(
    template_root: pathlib.Path,
    drawing_slug: Optional[str],
    sheet_number: Optional[str],
    meta: Dict[str, Any],
    client: Optional[OpenAI],
) -> List[Dict[str, Any]]:
    """Collect template documents for a specific sheet."""
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

