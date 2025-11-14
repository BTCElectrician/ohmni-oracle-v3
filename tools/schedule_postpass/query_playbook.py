#!/usr/bin/env python3
"""Developer-only sanity checks for the unified index upload."""
from __future__ import annotations

import json
import os
import sys
from typing import List, Optional

import requests

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
API_KEY = os.environ["AZURE_SEARCH_API_KEY"]
INDEX_NAME = os.environ.get("INDEX_NAME", "drawings_unified")
API_VERSION = "2024-07-01"

try:
    EMBEDDING_CLIENT = OpenAI() if OpenAI else None
except Exception as exc:  # pragma: no cover - relies on runtime creds
    print(f"Warning: OpenAI client unavailable ({exc}). Vector queries disabled.", file=sys.stderr)
    EMBEDDING_CLIENT = None


def _search_url(path: str) -> str:
    return f"{ENDPOINT}{path}?api-version={API_VERSION}"


def post_search(body: dict) -> dict:
    url = _search_url(f"/indexes/{INDEX_NAME}/docs/search")
    headers = {"Content-Type": "application/json", "api-key": API_KEY}
    try:
        response = requests.post(url, headers=headers, data=json.dumps(body))
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as exc:  # pragma: no cover - network side effects
        print(f"Search request failed: {exc}", file=sys.stderr)
        if getattr(exc, "response", None) is not None:
            print(f"Response: {exc.response.text}", file=sys.stderr)
        return {"value": []}


def generate_query_embedding(text: str) -> Optional[List[float]]:
    if not EMBEDDING_CLIENT or not text or not text.strip():
        return None
    try:
        resp = EMBEDDING_CLIENT.embeddings.create(model="text-embedding-3-small", input=text)
        return resp.data[0].embedding
    except Exception as exc:  # pragma: no cover
        print(f"Embedding generation failed: {exc}", file=sys.stderr)
        return None


def unified_search(search_text: str, search_filter: Optional[str] = None, top: int = 25) -> dict:
    base_body = {
        "search": search_text,
        "top": top,
        "queryType": "semantic",
        "semanticConfiguration": "semconf",
        "queryLanguage": "en-us",
        "includeTotalResultCount": True,
        "captions": "extractive",
        "answers": "extractive|count-3",
        "highlightFields": "content",
        "scoringProfile": "freshness_boost",
        "facet": [
            "discipline",
            "schedule_type",
            "levels",
            "template_status",
            "doc_type",
            "template_tags",
        ],
        "select": "id,doc_type,project,sheet_number,sheet_title,discipline,schedule_type,key,attributes,labels,revision,source_file,content,template_type,room_id,template_status",
    }
    query_vector = generate_query_embedding(search_text)
    if query_vector:
        base_body["vectorQueries"] = [
            {
                "vector": query_vector,
                "kNearestNeighborsCount": 50,
                "fields": "content_vector",
            }
        ]

    fact_filter = search_filter if search_filter else "doc_type eq 'fact'"
    fact_body = dict(base_body)
    fact_body["filter"] = fact_filter
    fact_res = post_search(fact_body)
    if fact_res.get("value"):
        print(f"--- Found {len(fact_res['value'])} matching FACTS ---", file=sys.stderr)
        return fact_res

    template_filter = search_filter if search_filter else "doc_type eq 'template'"
    template_body = dict(base_body)
    template_body["filter"] = template_filter
    template_res = post_search(template_body)
    if template_res.get("value"):
        print(
            f"--- No facts found, falling back to {len(template_res['value'])} TEMPLATES ---",
            file=sys.stderr,
        )
        return template_res

    if search_filter in (None, "doc_type eq 'fact'"):
        print("--- No facts or templates found, falling back to SHEETS ---", file=sys.stderr)
        sheet_body = dict(base_body)
        sheet_body["filter"] = "doc_type eq 'sheet'"
        return post_search(sheet_body)

    print("--- No specific results found, not falling back. ---", file=sys.stderr)
    return fact_res


def show(title: str, res: dict) -> None:
    print(f"\n=== {title} ===")
    total = res.get("@odata.count", len(res.get("value", [])))
    print(f"Total results: {total}")
    for idx, hit in enumerate(res.get("value", []), 1):
        doc_type = hit.get("doc_type")
        score = hit.get("@search.score", 0.0)
        print(f"\n{idx:2d}. [Score: {score:.2f}] [{doc_type}] {hit.get('content')}")
        if doc_type == "fact":
            print(f"    -> {hit.get('schedule_type')} | key={hit.get('key')} | sheet={hit.get('sheet_number')}")
        elif doc_type == "template":
            print(
                "    -> "
                f"{hit.get('template_type')} | room={hit.get('room_id')} | "
                f"status={hit.get('template_status')} | sheet={hit.get('sheet_number')}"
            )
        else:
            print(f"    -> sheet={hit.get('sheet_number')} | title={hit.get('sheet_title')}")


def main() -> None:
    print("--- Running query playbook (Developer Sanity Check) ---")
    print("--- NOTE: This script demonstrates the facts-first lookup logic. ---")
    print("--- Production query routing still lives in your Azure Function. ---")

    res1 = unified_search("dishwasher A4")
    show("Dishwasher in Unit A4 (Facts-first)", res1)

    template_filter = "doc_type eq 'template' and template_status eq 'signed_off'"
    res2 = unified_search("Unit A4 Kitchen", search_filter=template_filter, top=50)
    show("Signed-off templates in Unit A4 (Templates-only)", res2)

    panel_filter = "doc_type eq 'fact' and schedule_type eq 'panel' and key/panel eq 'S2'"
    res3 = unified_search("", search_filter=panel_filter, top=200)
    show("Panel S2 schedule (Facts-only, no fallback)", res3)

    res4 = unified_search("main riser diagram")
    show("Main Riser Diagram (May fall back to sheets)", res4)


if __name__ == "__main__":
    main()
