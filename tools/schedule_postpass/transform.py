#!/usr/bin/env python3
"""Post-process extracted schedule JSON into Azure Search docs."""
from __future__ import annotations

import argparse
import csv
import pathlib
import sys
from typing import Any, Dict, List

# Add parent directory to path when running as script
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

try:
    from .coverage import coverage_rows
    from .embeddings import create_embedding_client
    from .facts import emit_facts
    from .io_utils import load_json, write_jsonl
    from .metadata import make_sheet_doc, sheet_meta
    from .sheet_chunks import iter_sheet_chunks
    from .template_docs import PROJECT_ID_DEFAULT, _collect_sheet_templates, iter_template_docs
except ImportError:  # When executed as a script
    from tools.schedule_postpass.coverage import coverage_rows  # type: ignore
    from tools.schedule_postpass.embeddings import create_embedding_client  # type: ignore
    from tools.schedule_postpass.facts import emit_facts  # type: ignore
    from tools.schedule_postpass.io_utils import load_json, write_jsonl  # type: ignore
    from tools.schedule_postpass.metadata import make_sheet_doc, sheet_meta  # type: ignore
    from tools.schedule_postpass.sheet_chunks import iter_sheet_chunks  # type: ignore
    from tools.schedule_postpass.template_docs import PROJECT_ID_DEFAULT, _collect_sheet_templates, iter_template_docs  # type: ignore


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
        embedding_client = create_embedding_client()
    except Exception as exc:  # pragma: no cover - depends on env
        print(f"Warning: Unable to initialize OpenAI client ({exc}). Embeddings disabled.", file=sys.stderr)
        embedding_client = None

    output_dir.mkdir(parents=True, exist_ok=True)
    sheets_jsonl = output_dir / "sheets.jsonl"
    facts_jsonl = output_dir / "facts.jsonl"
    templates_jsonl = output_dir / "templates.jsonl"
    drawings_jsonl = output_dir / "drawings_unified.jsonl"
    coverage_csv = output_dir / "coverage_report.csv"

    all_sheets: List[Dict[str, Any]] = []
    all_facts: List[Dict[str, Any]] = []
    all_templates: List[Dict[str, Any]] = []
    drawings_docs: List[Dict[str, Any]] = []

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
            sheet_chunks = list(iter_sheet_chunks(raw, meta, embedding_client))
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
            drawings_docs.extend(sheet_chunks)
            drawings_docs.extend(facts)
            coverage_rows_data.extend(coverage_rows(sheet_doc, facts, templates_for_sheet))

        write_jsonl(sheets_jsonl, all_sheets)
        write_jsonl(facts_jsonl, all_facts)
        write_jsonl(drawings_jsonl, drawings_docs)
        print(f"Wrote {len(all_sheets)} sheets -> {sheets_jsonl}")
        print(f"Wrote {len(all_facts)} schedule rows -> {facts_jsonl}")
        chunk_docs = sum(1 for doc in drawings_docs if doc.get("doc_type") == "sheet_chunk")
        schedule_rows = sum(1 for doc in drawings_docs if doc.get("doc_type") == "schedule_row")
        print(
            f"Wrote {chunk_docs + schedule_rows} drawings docs "
            f"({chunk_docs} chunks, {schedule_rows} rows) -> {drawings_jsonl}"
        )
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
