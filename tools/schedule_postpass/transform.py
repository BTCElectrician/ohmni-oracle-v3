#!/usr/bin/env python3
"""Post-process extracted schedule JSON into Azure Search docs."""
from __future__ import annotations

import argparse
import csv
import json
import logging
import pathlib
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

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


def sheet_meta(raw: Dict[str, Any], project_id: str) -> Dict[str, Any]:
    return {
        "project": raw.get("project_name") or raw.get("project") or project_id or "Unnamed Project",
        "project_id": project_id,
        "sheet_number": raw.get("sheet_number"),
        "sheet_title": raw.get("sheet_title") or "",
        "discipline": (raw.get("discipline") or "").lower() or "architectural",
        "revision": raw.get("revision") or "IFC",
        "revision_date": raw.get("revision_date") or "2000-01-01",
        "levels": raw.get("levels") or [],
        "source_file": raw.get("source_file") or "<blob/path>.pdf",
        "content": raw.get("content", ""),
    }


def make_sheet_doc(meta: Dict[str, Any], raw_json: Dict[str, Any], client: Optional[OpenAI]) -> Dict[str, Any]:
    doc = {
        "id": f"{meta['project_id']}|{meta['sheet_number']}|{meta['revision']}",
        "doc_type": "sheet",
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
                "id": f"{meta['project_id']}|{meta['sheet_number']}|{meta['revision']}|row:{stable_key(stype, key)}",
                "doc_type": "fact",
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
) -> Iterable[Dict[str, Any]]:
    for path in sorted(template_root.rglob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            print(f"Skipping malformed template {path}: {exc}", file=sys.stderr)
            continue

        template_type = raw.get("template_type") or _guess_template_type(path)
        sheet_number = raw.get("sheet_number") or path.parent.name
        room_id = raw.get("room_id") or path.stem
        if not sheet_number or not room_id:
            print(f"Skipping template {path}: Missing sheet_number or room_id.", file=sys.stderr)
            continue

        summary = build_template_summary(template_type, raw)
        revision = raw.get("revision") or base_meta.get("revision") or "IFC"
        revision_date = raw.get("revision_date") or base_meta.get("revision_date") or "2000-01-01"
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

        doc = {
            "id": f"{project_id}|{sheet_number}|{room_id}|template:{template_type}",
            "doc_type": "template",
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
        embedding = generate_embedding(summary, client)
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
    sheet_number: Optional[str],
    meta: Dict[str, Any],
    client: Optional[OpenAI],
) -> List[Dict[str, Any]]:
    if not sheet_number:
        return []
    results: List[Dict[str, Any]] = []
    for discipline in ("electrical", "architectural"):
        sheet_dir = template_root / discipline / sheet_number
        if sheet_dir.exists():
            results.extend(list(iter_template_docs(sheet_dir, meta, client)))
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
        for json_path in sorted(input_dir.rglob("*.json")):
            raw = load_json(json_path)
            meta = sheet_meta(raw, project_id)
            sheet_doc = make_sheet_doc(meta, raw, embedding_client)
            facts = list(emit_facts(raw, meta, embedding_client))
            templates_for_sheet = _collect_sheet_templates(template_root, meta.get("sheet_number"), meta, embedding_client)

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
