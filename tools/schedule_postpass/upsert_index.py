#!/usr/bin/env python3
"""Create or update the Azure AI Search index and upload JSONL docs."""
from __future__ import annotations

import argparse
import json
import os
import pathlib
from typing import Optional

import requests

AZURE_SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
AZURE_SEARCH_API_KEY = os.environ["AZURE_SEARCH_API_KEY"]
INDEX_NAME = os.environ.get("INDEX_NAME", "drawings_unified")
API_VERSION = os.environ.get("AZURE_SEARCH_API_VERSION", "2024-07-01")


def _index_url(path: str) -> str:
    delimiter = "" if AZURE_SEARCH_ENDPOINT.endswith("/") else "/"
    base = f"{AZURE_SEARCH_ENDPOINT}{delimiter}{path.lstrip('/')}"
    return f"{base}?api-version={API_VERSION}"


def create_index(schema_path: pathlib.Path) -> None:
    url = _index_url(f"/indexes/{INDEX_NAME}")
    headers = {"Content-Type": "application/json", "api-key": AZURE_SEARCH_API_KEY}
    try:
        schema = json.loads(schema_path.read_text())
    except FileNotFoundError:
        raise FileNotFoundError(f"Schema file not found at {schema_path}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"Schema file {schema_path} is not valid JSON: {exc}")

    print(f"Attempting to create/update index '{INDEX_NAME}'...")
    response = requests.put(url, headers=headers, data=json.dumps(schema))
    if response.status_code not in (200, 201, 204):
        raise RuntimeError(f"Index create failed: {response.status_code} {response.text}")
    print("Index created/replaced.")


def create_synonym_map(synonyms_path: pathlib.Path) -> None:
    url = _index_url("/synonymmaps/project-synonyms")
    headers = {"Content-Type": "application/json", "api-key": AZURE_SEARCH_API_KEY}
    try:
        raw_payload = json.loads(synonyms_path.read_text())
    except FileNotFoundError:
        raise FileNotFoundError(f"Synonym file not found at {synonyms_path}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"Synonym file {synonyms_path} is not valid JSON: {exc}")

    if isinstance(raw_payload, dict) and isinstance(raw_payload.get("synonyms"), list):
        lines = []
        for entry in raw_payload["synonyms"]:
            if not isinstance(entry, dict):
                continue
            from_terms = entry.get("from") or []
            to_term: Optional[str] = entry.get("to")
            if from_terms and to_term:
                lines.append(f"{', '.join(from_terms)} => {to_term}")
        payload = {
            "name": "project-synonyms",
            "format": "solr",
            "synonyms": "\n".join(lines),
        }
    else:
        payload = dict(raw_payload)
        payload.setdefault("name", "project-synonyms")
        payload.setdefault("format", "solr")

    print("Creating/updating synonym map 'project-synonyms'...")
    response = requests.put(url, headers=headers, data=json.dumps(payload))
    if response.status_code == 409:
        headers["If-Match"] = "*"
        response = requests.put(url, headers=headers, data=json.dumps(payload))
    if response.status_code not in (200, 201, 204):
        raise RuntimeError(f"Synonym map create failed: {response.status_code} {response.text}")
    print("Synonym map ready.")


def upload_jsonl(jsonl_path: pathlib.Path, batch_size: int = 1000) -> None:
    if not jsonl_path:
        return
    if not jsonl_path.exists():
        print(f"Skipping upload: {jsonl_path} not found.")
        return

    url = _index_url(f"/indexes/{INDEX_NAME}/docs/index")
    headers = {"Content-Type": "application/json", "api-key": AZURE_SEARCH_API_KEY}
    batch = []
    count = 0
    print(f"Uploading {jsonl_path.name}...")
    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            doc = json.loads(line)
            doc.pop("raw_json", None)
            batch.append({"@search.action": "mergeOrUpload", **doc})
            count += 1
            if len(batch) >= batch_size:
                response = requests.post(url, headers=headers, data=json.dumps({"value": batch}))
                if response.status_code not in (200, 201):
                    raise RuntimeError(f"Upload error: {response.status_code} {response.text}")
                batch = []
    if batch:
        response = requests.post(url, headers=headers, data=json.dumps({"value": batch}))
        if response.status_code not in (200, 201):
            raise RuntimeError(f"Upload error: {response.status_code} {response.text}")
    print(f"Uploaded {count} documents from {jsonl_path.name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", required=True, help="path to unified_index.schema.json")
    parser.add_argument("--sheets", default="", help="path to sheets.jsonl")
    parser.add_argument("--facts", default="", help="path to facts.jsonl")
    parser.add_argument("--templates", default="", help="path to templates.jsonl")
    parser.add_argument("--synonyms", default="", help="path to synonyms.seed.json")
    parser.add_argument(
        "--mode",
        default="full",
        choices=["full", "incremental"],
        help="full rebuild (recreate index) or incremental upload",
    )
    args = parser.parse_args()

    if args.mode == "full":
        if args.synonyms:
            create_synonym_map(pathlib.Path(args.synonyms))
        create_index(pathlib.Path(args.schema))
    else:
        print("Incremental mode selected: Skipping index creation/replacement.")

    if args.sheets:
        upload_jsonl(pathlib.Path(args.sheets))
    if args.facts:
        upload_jsonl(pathlib.Path(args.facts))
    if args.templates:
        upload_jsonl(pathlib.Path(args.templates))

    print("All done.")


if __name__ == "__main__":
    main()
