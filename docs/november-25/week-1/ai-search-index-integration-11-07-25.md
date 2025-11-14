Got it. I'll merge the original PRD with all the requested document updates, including the new sections on mandatory template inputs, the updated schema, the enhanced `transform.py` and `upsert_index.py` functionality, and the revised `README.md`.

Here is the **100% complete, unified PRD** ready for copy-paste.

-----

Locked and loaded. Here’s the **one-shot, everything-in-one** project pack—no cross-referencing needed.

I've merged all requirements and updated the `README.md` (section 11) to reflect our clarification: the `query_playbook.py` is a **developer-only sanity check**, not the production query logic.

Copy this whole message into a `.md` in your repo and you’re off to the races.

-----

# Schedule-Only MVP — One Unified Index (Sheets + Row-Facts + Templates)

## 1\) Folder layout to create

This is the complete drop-in package.

```
/tools/schedule_postpass/
  transform.py                # post-pass: sheet JSON -> facts JSONL (+ coverage CSV)
  parsers.py                  # blunt row extractors per schedule_type
  synonyms.seed.json          # expanded synonym map
  unified_index.schema.json   # the single, unified Azure AI Search schema
  upsert_index.py             # create Azure index + upload docs (sheets + facts + templates)
  query_playbook.py           # developer-only sanity check for the data load
  README.md                   # how-to, end-to-end steps (UPDATED)
  tests/
    test_postpass.py          # sanity tests against sample JSON
```

-----

## 2\) Integration plan updates (11-07-25)

  * `tools/schedule_postpass/` is the drop-in package your processing script should call right after OCR to keep the pipeline deterministic.
  * The `query_playbook.py` script provides a simple developer test to verify the data load. The *real* query logic (the "facts-first, sheets-fallback" pattern) will be implemented in your existing Azure Function.
  * The one-index design (`drawings_unified`) remains required. `doc_type` partitions sheets vs. row facts vs. templates.
  * Load `synonyms.seed.json` into an Azure AI Search synonym map and attach it to the searchable fields (a one-time setup).
  * Basic tier ($75/mo) supports semantic ranking (1K semantic queries/month free), hybrid vector search, scoring profiles, facets, suggesters, and synonym maps. Fresh embeddings via `text-embedding-3-small` run about $0.02 per million tokens, so even big refreshes stay well under $1.
  * **Template JSON** (electrical + architectural) now rides the same deterministic pipeline: copy the filled templates into the run folder and pass `--templates-root` to `transform.py` so each index refresh includes the foreman-authored truth.
  * Bake the `README.md` + `pytest` from this folder into the PRD acceptance criteria so anyone can follow the runbook and CI can catch regressions.

-----

## 3\) Mandatory template inputs (`templates/e_rooms_template.json`, `templates/a_rooms_template.json`)

  * These two base templates live in `templates/` and serve as scaffolds for room-by-room data collection.
  * **Electrical template (`e_rooms_template.json`)** is comprehensive and tracks: circuits (lighting/power/emergency/critical/UPS), light fixtures, outlets (regular/controlled/GFCI/USB/hospital-grade), switches, fire alarm devices (smoke/heat detectors, pull stations, horn/strobes), data/telecom (data outlets, wireless AP), security (cameras, card readers, panic buttons), audiovisual (displays, projectors, speakers, control panels), nurse call (stations, pull cords, dome lights, code blue), medical gas (O2, vacuum, medical air, WAGD), lab systems (fume hoods, biosafety cabinets, emergency showers), data center (racks, PDUs, cooling, EPO), and kitchen systems (hood suppression, grease trap alarms).
  * **Architectural template (`a_rooms_template.json`)** is comprehensive and tracks: dimensions, walls (by orientation with fire/STC ratings), doors/windows, finishes (floor/wall/ceiling with materials and colors), casework, specialties (toilet accessories, signage, whiteboards, grab bars), accessibility (ADA compliance), fire/life safety (ratings, dampers, occupancy classification), acoustics (STC requirements, sound masking), HVAC integration (diffusers, thermostats, VAV boxes), plumbing fixtures, and special room configurations (clean rooms, labs, food service, data centers, operating rooms).
  * During floor plan processing, your script auto-generates one electrical + one architectural JSON file per detected room. Foremen then populate these pre-generated files with actual device counts, fixture info, and finish details using voice/chatbot interface.
  * They are the human-in-the-loop source of truth until CV models can infer every device on a sheet, so do not treat them as optional sidecars.
  * For each run, copy the electrical template to a job-scoped folder such as `processing/<project>/templates/electrical/<sheet>/<room>.json` and do the same for the architectural template (`.../architectural/...`). Foremen fill these JSON files directly; version them in Git/LFS or sync them from the field tablets so nothing lives only on one laptop.
  * The processing script must pass the root of those filled-in templates to `transform.py` so we can emit template docs alongside sheets and row-facts. When a foreman edits a template, rerun the emitter (or the incremental sync described later) to merge the update.
  * The template schema stays intentionally loose: you can add as many keys as you need (new fixture counts, specialty devices, finish notes, etc.) without changing the search index schema each time. We snapshot the full JSON body into `template_payload` while also surfacing the high-signal fields for filtering.

### Minimum metadata per template doc

| Field | Required | Notes |
| :--- | :--- | :--- |
| `template_type` | yes | `electrical` for `e_rooms_template.json`, `architectural` for `a_rooms_template.json` |
| `template_id` | yes | Deterministic string, e.g., `<sheet_number>-<room_id>-<template_type>` |
| `sheet_number` | yes | Must match the sheet feeding the template |
| `room_id` / `room_name` | yes | Whatever the foreman uses in the field (unit, space, etc.) |
| `project_id` / `project` | yes | Same as the sheet + fact docs |
| `levels` | optional | Carry the level/zone so we can facet by floor |
| `template_status` | optional | `in_progress`, `ready_for_review`, `signed_off`, etc. |
| `template_author` | optional | Foreman initials or AD handle |
| `template_last_modified` | optional | ISO timestamp so we can sort by freshest edits |
| `template_tags` | optional | Free-form labels derived from the payload (e.g., `lighting`, `critical_load`) |
| `template_payload` | yes | `json.dumps()` of the filled template so the schema can expand without reindexing |

### Example template doc emitted to JSONL

```json
{
  "id": "veridian|E2.03|A4|template:electrical",
  "doc_type": "template",
  "template_type": "electrical",
  "template_id": "E2.03-A4-electrical",
  "project": "Veridian Block 1",
  "project_id": "veridian",
  "sheet_number": "E2.03",
  "levels": ["Level 2"],
  "room_id": "A4",
  "room_name": "Unit A4 Kitchen",
  "discipline": "electrical",
  "template_status": "in_progress",
  "template_author": "jfernandez",
  "template_last_modified": "2025-02-12T09:14:00Z",
  "template_tags": ["lighting", "outlets", "gfci", "appliances", "fire_alarm", "data"],
  "content": "A4 Electrical — Lighting: L47, L48, 10 outlets, 1 FA devices, 6 data (in_progress)",
  "template_payload": "{\"room_id\":\"A4\",\"room_name\":\"Unit A4 Kitchen\",\"sheet_number\":\"E2.03\",\"levels\":[\"Level 2\"],\"template_status\":\"in_progress\",\"circuits\":{\"lighting\":[\"L47\",\"L48\"],\"power\":[\"P12\"],\"emergency\":[]},\"light_fixtures\":{\"fixture_ids\":[\"A\",\"B\"],\"fixture_count\":{\"A\":2,\"B\":2}},\"outlets\":{\"regular_outlets\":6,\"controlled_outlets\":2,\"gfci_outlets\":2},\"appliances\":[\"DW\",\"Range\"],\"fire_alarm\":{\"smoke_detectors\":{\"count\":1,\"type\":\"photoelectric\",\"locations\":[\"ceiling\"]},\"horn_strobes\":{\"count\":0}},\"data_telecom\":{\"data_outlets\":6,\"wireless_ap\":false},\"discrepancies\":[],\"field_notes\":\"\"}"
}
```

The `content` field stays a short, human-readable summary (used by Search and the chatbot). `template_payload` stores the entire JSON body escaped as a string so future AI models can overwrite it without schema churn. When the CV models eventually replace the manual process, just drop their outputs into the same template files and rerun the sync.

-----

## 4\) `tools/schedule_postpass/unified_index.schema.json`

> Name your index e.g. `drawings_unified`. This carries **sheets**, **facts**, and **templates**. The embedding dimension is locked to 1536 for `text-embedding-3-small`.

```json
{
  "name": "drawings_unified",
  "fields": [
    {"name":"id","type":"Edm.String","key":true,"searchable":false,"filterable":true,"sortable":false,"facetable":false},
    {"name":"doc_type","type":"Edm.String","searchable":false,"filterable":true,"sortable":true,"facetable":true},

    /* TEMPLATE metadata */
    {"name":"template_type","type":"Edm.String","searchable":false,"filterable":true,"sortable":true,"facetable":true},
    {"name":"template_id","type":"Edm.String","searchable":false,"filterable":true,"sortable":true,"facetable":true},
    {"name":"room_id","type":"Edm.String","searchable":true,"filterable":true,"sortable":true,"facetable":true,"synonymMaps":["project-synonyms"]},
    {"name":"room_name","type":"Edm.String","searchable":true,"filterable":true,"sortable":false,"facetable":false,"synonymMaps":["project-synonyms"]},
    {"name":"template_status","type":"Edm.String","searchable":false,"filterable":true,"sortable":true,"facetable":true},
    {"name":"template_author","type":"Edm.String","searchable":false,"filterable":true,"sortable":true,"facetable":true},
    {"name":"template_last_modified","type":"Edm.DateTimeOffset","searchable":false,"filterable":true,"sortable":true,"facetable":false},
    {"name":"template_tags","type":"Collection(Edm.String)","searchable":true,"filterable":true,"sortable":false,"facetable":true,"synonymMaps":["project-synonyms"]},
    {"name":"template_payload","type":"Edm.String","searchable":true,"filterable":false,"sortable":false,"facetable":false,"synonymMaps":["project-synonyms"]},

    {"name":"project","type":"Edm.String","searchable":true,"filterable":true,"sortable":true,"facetable":true,"synonymMaps":["project-synonyms"]},
    {"name":"project_id","type":"Edm.String","searchable":false,"filterable":true,"sortable":true,"facetable":true},

    {"name":"sheet_number","type":"Edm.String","searchable":true,"filterable":true,"sortable":true,"facetable":true,"synonymMaps":["project-synonyms"]},
    {"name":"sheet_title","type":"Edm.String","searchable":true,"filterable":false,"sortable":false,"facetable":false,"synonymMaps":["project-synonyms"]},
    {"name":"discipline","type":"Edm.String","searchable":false,"filterable":true,"sortable":true,"facetable":true},

    {"name":"revision","type":"Edm.String","searchable":false,"filterable":true,"sortable":true,"facetable":true},
    {"name":"revision_date","type":"Edm.DateTimeOffset","searchable":false,"filterable":true,"sortable":true,"facetable":false},

    {"name":"levels","type":"Collection(Edm.String)","searchable":false,"filterable":true,"sortable":false,"facetable":true},

    {"name":"source_file","type":"Edm.String","searchable":false,"filterable":false,"sortable":false,"facetable":false},

    /* SHEET/TEMPLATE/FACT content */
    {"name":"content","type":"Edm.String","searchable":true,"filterable":false,"sortable":false,"facetable":false,"synonymMaps":["project-synonyms"]},
    {"name":"content_vector","type":"Collection(Edm.Single)","searchable":true,"dimensions":1536,"vectorSearchProfile":"vprof","filterable":false,"sortable":false,"facetable":false},

    /* FACT fields */
    {"name":"schedule_type","type":"Edm.String","searchable":false,"filterable":true,"sortable":true,"facetable":true},

    {"name":"key","type":"Edm.ComplexType","fields":[
      {"name":"panel","type":"Edm.String","searchable":true,"filterable":true,"sortable":true,"facetable":true,"synonymMaps":["project-synonyms"]},
      {"name":"circuit","type":"Edm.String","searchable":true,"filterable":true,"sortable":true,"facetable":true,"synonymMaps":["project-synonyms"]},
      {"name":"unit","type":"Edm.String","searchable":true,"filterable":true,"sortable":true,"facetable":true,"synonymMaps":["project-synonyms"]},
      {"name":"tag","type":"Edm.String","searchable":true,"filterable":true,"sortable":true,"facetable":true,"synonymMaps":["project-synonyms"]},
      {"name":"wall_type","type":"Edm.String","searchable":true,"filterable":true,"sortable":true,"facetable":true,"synonymMaps":["project-synonyms"]},
      {"name":"fixture_type","type":"Edm.String","searchable":true,"filterable":true,"sortable":true,"facetable":true,"synonymMaps":["project-synonyms"]},
      {"name":"door_number","type":"Edm.String","searchable":true,"filterable":true,"sortable":true,"facetable":true,"synonymMaps":["project-synonyms"]},
      {"name":"ceiling_type","type":"Edm.String","searchable":true,"filterable":true,"sortable":true,"facetable":true,"synonymMaps":["project-synonyms"]}
    ]},

    {"name":"attributes","type":"Edm.ComplexType","fields":[
      {"name":"description","type":"Edm.String","searchable":true,"filterable":false,"sortable":false,"facetable":false,"synonymMaps":["project-synonyms"]},
      {"name":"voltage","type":"Edm.Double","searchable":false,"filterable":true,"sortable":true,"facetable":false},
      {"name":"phase","type":"Edm.String","searchable":false,"filterable":true,"sortable":true,"facetable":true},
      {"name":"rating_a","type":"Edm.Double","searchable":false,"filterable":true,"sortable":true,"facetable":false},
      {"name":"wire","type":"Edm.String","searchable":true,"filterable":false,"sortable":false,"facetable":false,"synonymMaps":["project-synonyms"]},
      {"name":"conduit","type":"Edm.String","searchable":true,"filterable":false,"sortable":false,"facetable":false,"synonymMaps":["project-synonyms"]},
      {"name":"hp","type":"Edm.Double","searchable":false,"filterable":true,"sortable":true,"facetable":false},
      {"name":"kw","type":"Edm.Double","searchable":false,"filterable":true,"sortable":true,"facetable":false},
      {"name":"kva","type":"Edm.Double","searchable":false,"filterable":true,"sortable":true,"facetable":false},
      {"name":"mca","type":"Edm.Double","searchable":false,"filterable":true,"sortable":true,"facetable":false},
      {"name":"mop","type":"Edm.Double","searchable":false,"filterable":true,"sortable":true,"facetable":false},
      {"name":"fla","type":"Edm.Double","searchable":false,"filterable":true,"sortable":true,"facetable":false},
      {"name":"busbar_a","type":"Edm.Double","searchable":false,"filterable":true,"sortable":true,"facetable":false},
      {"name":"disconnect","type":"Edm.String","searchable":true,"filterable":true,"sortable":false,"facetable":true,"synonymMaps":["project-synonyms"]},
      {"name":"panel","type":"Edm.String","searchable":true,"filterable":true,"sortable":true,"facetable":true,"synonymMaps":["project-synonyms"]},
      {"name":"circuit","type":"Edm.String","searchable":true,"filterable":true,"sortable":true,"facetable":true,"synonymMaps":["project-synonyms"]},
      
      {"name":"lumens","type":"Edm.Double","searchable":false,"filterable":true,"sortable":true,"facetable":false},
      {"name":"lamp_type","type":"Edm.String","searchable":true,"filterable":true,"sortable":true,"facetable":true,"synonymMaps":["project-synonyms"]},
      {"name":"cct","type":"Edm.String","searchable":true,"filterable":true,"sortable":true,"facetable":true,"synonymMaps":["project-synonyms"]},
      {"name":"cri","type":"Edm.String","searchable":true,"filterable":true,"sortable":true,"facetable":true,"synonymMaps":["project-synonyms"]},
      {"name":"mounting","type":"Edm.String","searchable":true,"filterable":true,"sortable":true,"facetable":true,"synonymMaps":["project-synonyms"]},
      {"name":"dimming","type":"Edm.String","searchable":true,"filterable":true,"sortable":true,"facetable":true,"synonymMaps":["project-synonyms"]},
      
      {"name":"stc","type":"Edm.Double","searchable":false,"filterable":true,"sortable":true,"facetable":false},
      {"name":"fire_rating","type":"Edm.String","searchable":true,"filterable":true,"sortable":true,"facetable":true,"synonymMaps":["project-synonyms"]},
      {"name":"stud_gauge","type":"Edm.String","searchable":true,"filterable":false,"sortable":false,"facetable":false,"synonymMaps":["project-synonyms"]},
      {"name":"layers","type":"Edm.String","searchable":true,"filterable":false,"sortable":false,"facetable":false,"synonymMaps":["project-synonyms"]},
      
      {"name":"ceiling_height_in","type":"Edm.Double","searchable":false,"filterable":true,"sortable":true,"facetable":false},
      {"name":"finish_floor","type":"Edm.String","searchable":true,"filterable":true,"sortable":true,"facetable":true,"synonymMaps":["project-synonyms"]},
      {"name":"finish_wall","type":"Edm.String","searchable":true,"filterable":true,"sortable":true,"facetable":true,"synonymMaps":["project-synonyms"]},
      {"name":"finish_ceiling","type":"Edm.String","searchable":true,"filterable":true,"sortable":true,"facetable":true,"synonymMaps":["project-synonyms"]},
      {"name":"acoustic","type":"Edm.String","searchable":true,"filterable":false,"sortable":false,"facetable":false,"synonymMaps":["project-synonyms"]},
      {"name":"grid","type":"Edm.String","searchable":true,"filterable":false,"sortable":false,"facetable":false,"synonymMaps":["project-synonyms"]},

      {"name":"hardware_set","type":"Edm.String","searchable":true,"filterable":true,"sortable":true,"facetable":true,"synonymMaps":["project-synonyms"]},
      {"name":"size","type":"Edm.String","searchable":true,"filterable":false,"sortable":false,"facetable":false,"synonymMaps":["project-synonyms"]},
      {"name":"material_frame","type":"Edm.String","searchable":true,"filterable":false,"sortable":false,"facetable":false,"synonymMaps":["project-synonyms"]},

      {"name":"btu","type":"Edm.Double","searchable":false,"filterable":true,"sortable":true,"facetable":false},
      {"name":"gpm","type":"Edm.Double","searchable":false,"filterable":true,"sortable":true,"facetable":false},
      {"name":"head","type":"Edm.Double","searchable":false,"filterable":true,"sortable":true,"facetable":false}
    ]},

    {"name":"labels","type":"Collection(Edm.String)","searchable":true,"filterable":true,"sortable":false,"facetable":true,"synonymMaps":["project-synonyms"]},
    {"name":"source_bbox","type":"Collection(Edm.Double)","searchable":false,"filterable":false,"sortable":false,"facetable":false}
  ],
  "vectorSearch": {
    "algorithms": [{"name":"hnsw","kind":"hnsw","parameters":{"m":32,"efConstruction":400}}],
    "profiles": [{"name":"vprof","algorithm":"hnsw","vectorizer":"none"}]
  },
  "semantic": {
    "configurations": [{
      "name": "semconf",
      "prioritizedFields": {
        "titleField": {"fieldName": "sheet_number"},
        "contentFields": [{"fieldName":"content"}]
      }
    }]
  },
  "suggesters": [{
    "name": "sg",
    "searchMode": "analyzingInfixMatching",
    "sourceFields": ["sheet_number","sheet_title","room_id","room_name","key/panel","key/tag"]
  }],
  "scoringProfiles": [{
    "name":"freshness_boost",
    "functions":[{"type":"freshness","fieldName":"revision_date","interpolation":"quadratic","boost":1.2,"freshness":{"boostingDuration":"P365D"}}]
  }]
}
```

Template docs share the same index as sheets + facts: `content` carries the short summary, while the dedicated `template_*` fields keep the human-in-the-loop metadata filterable. Because `template_payload` holds the entire JSON snapshot, foremen can add new keys (extra counts, specialty devices, finish notes, etc.) without forcing a schema migration—Search just stores the blob until we decide to project new fields out of it.

-----

## 5\) `tools/schedule_postpass/transform.py`

`transform.py` now expects the filled template directory as part of every run so we can emit `templates.jsonl` next to `sheets.jsonl` and `facts.jsonl`. The CLI preserves the original positional args and adds a required flag for the templates root plus an optional `--templates-only` mode for foreman edits.

```bash
python tools/schedule_postpass/transform.py \
  /path/to/sheet_json_folder \
  /tmp/out \
  veridian \
  --templates-root /path/to/job/templates \
  [--templates-only]
```

  * `--templates-root` points at the folder that contains the job's copies of the electrical + architectural room templates (organize by sheet/room however you like under that root).
  * `transform.py` scans both disciplines, emits one `doc_type="template"` record per filled JSON, and writes them to `/tmp/out/templates.jsonl`.
  * When `--templates-only` is set we skip the sheet/fact parsing logic and just produce template docs—useful when a foreman edits a handful of rooms and you want to re-upload without re-OCR-ing the whole set.
  * `coverage_report.csv` now appends template-level stats (room count per sheet, last modified, % of rooms marked `signed_off`).

<!-- end list -->

```python
#!/usr/bin/env python3
import json, sys, pathlib, csv, logging
from typing import Dict, Any, Iterable, List, Optional
from openai import OpenAI
from parsers import (
    classify_schedule_block, extract_key, extract_attributes, build_summary,
    build_template_summary, derive_template_tags
) # Note: parsers.py now needs new functions

import argparse
from datetime import datetime, timezone

PROJECT_ID_DEFAULT = "veridian"
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_embedding(text: str, client: Optional[OpenAI]) -> Optional[List[float]]:
    """Generate a vector embedding for hybrid search."""
    if not client or not text:
        return None
    trimmed = text.strip()
    if not trimmed:
        return None
    try:
        resp = client.embeddings.create(
            model="text-embedding-3-small",
            input=trimmed
        )
        return resp.data[0].embedding
    except Exception as exc:
        logger.warning(f"Embedding generation failed (skipping vector): {exc}")
        return None

def load_json(p: pathlib.Path) -> Dict[str, Any]:
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

def sheet_meta(raw: Dict[str, Any], project_id: str) -> Dict[str, Any]:
    return {
        "project": raw.get("project_name") or raw.get("project") or "Unnamed Project",
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

def make_sheet_doc(meta: Dict[str, Any], raw_json: Dict[str, Any], client: Optional[OpenAI] = None) -> Dict[str, Any]:
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
        "raw_json": raw_json # This will be popped by upsert_index.py
    }
    embedding = generate_embedding(doc.get("content", ""), client)
    if embedding:
        doc["content_vector"] = embedding
    return doc

def leftpad_circuit(s: Any) -> str:
    try:
        return f"{int(str(s).strip()):03d}"
    except:
        return str(s)

def stable_key(schedule_type: str, key_obj: Dict[str, Any]) -> str:
    parts = [schedule_type]
    for k in sorted(key_obj.keys()):
        v = key_obj[k]
        if k == "circuit":
            v = leftpad_circuit(v)
        parts.append(f"{k}-{v}")
    return "_".join(parts)

def emit_facts(raw_json: Dict[str, Any], meta: Dict[str, Any], client: Optional[OpenAI] = None) -> Iterable[Dict[str, Any]]:
    blocks = raw_json.get("blocks", [])
    for blk in blocks:
        stype = classify_schedule_block(blk)
        if not stype:
            continue
        for row in blk.get("rows", []):
            key = extract_key(stype, row)
            if not key:
                continue
            attrs = extract_attributes(stype, row)
            summary = build_summary(stype, key, attrs)
            skey = stable_key(stype, key)
            doc = {
                "id": f"{meta['project_id']}|{meta['sheet_number']}|{meta['revision']}|row:{skey}",
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
                "labels": attrs.pop("_labels", []), # Pop labels from attributes
                "content": summary
            }
            # carry bbox if present on row
            if "bbox_norm" in row:
                doc["source_bbox"] = row["bbox_norm"]
            embedding = generate_embedding(summary, client)
            if embedding:
                doc["content_vector"] = embedding
            yield doc


def iter_template_docs(template_root: pathlib.Path,
                       base_meta: Dict[str, Any],
                       client: Optional[OpenAI] = None) -> Iterable[Dict[str, Any]]:
    """Iterates through all template JSON files and yields template documents."""
    for path in sorted(template_root.rglob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Skipping malformed or missing template file: {path} ({e})", file=sys.stderr)
            continue
            
        template_type = "architectural" if "a_rooms" in path.name else "electrical"
        
        # Fallbacks for mandatory fields
        sheet_num = raw.get("sheet_number") or path.parent.name # Try sheet number from JSON or folder name
        room_id = raw.get("room_id") or path.stem
        
        # Skip if we can't determine basic identity
        if not sheet_num or not room_id:
            print(f"Skipping template {path}: Missing sheet_number or room_id.", file=sys.stderr)
            continue

        summary = build_template_summary(template_type, raw)
        
        # Use sheet revision/date if not present on template, for consistency
        revision = raw.get("revision") or base_meta.get("revision") or "IFC"
        last_modified = raw.get("template_last_modified") or raw.get("last_modified") or datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        doc = {
            **{k: base_meta[k] for k in base_meta if k not in ("sheet_title", "content", "revision", "revision_date", "source_file")}, # Inherit base meta except for sheet-specific fields
            "id": f"{base_meta['project_id']}|{sheet_num}|{room_id}|template:{template_type}",
            "doc_type": "template",
            "template_type": template_type,
            "template_id": raw.get("template_id") or f"{sheet_num}-{room_id}-{template_type}",
            "sheet_number": sheet_num,
            "room_id": room_id,
            "room_name": raw.get("room_name", ""),
            "discipline": raw.get("discipline") or ("electrical" if template_type == "electrical" else "architectural"),
            "levels": raw.get("levels") or base_meta.get("levels") or [],
            "revision": revision,
            "revision_date": raw.get("revision_date") or base_meta.get("revision_date") or "2000-01-01",
            "template_status": raw.get("template_status", "in_progress"),
            "template_author": raw.get("template_author"),
            "template_last_modified": last_modified,
            "template_tags": sorted(set(raw.get("template_tags", []) + derive_template_tags(raw))),
            "content": summary,
            "template_payload": json.dumps(raw, ensure_ascii=False)
        }
        embedding = generate_embedding(summary, client)
        if embedding:
            doc["content_vector"] = embedding
        yield doc


def write_jsonl(p: pathlib.Path, docs: Iterable[Dict[str, Any]]):
    with p.open("w", encoding="utf-8") as f:
        for d in docs:
            # Pop raw_json before writing, it's not needed in the JSONL
            d.pop("raw_json", None)
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

def coverage_rows(sheet_doc: Dict[str, Any], facts: List[Dict[str, Any]], templates: List[Dict[str, Any]]) -> List[List[str]]:
    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for f in facts:
        by_type.setdefault(f["schedule_type"], []).append(f)
    
    # Calculate fact metrics
    rows = []
    for stype, items in by_type.items():
        n_total = len(items)
        n_with_key = sum(1 for x in items if x.get("key")) # Simple check if key exists and is not empty
        n_with_pc = sum(1 for x in items if x["key"].get("panel") and x["key"].get("circuit"))
        n_with_v  = sum(1 for x in items if (x.get("attributes") or {}).get("voltage") is not None)
        n_with_mca_mop = sum(1 for x in items if (x.get("attributes") or {}).get("mca") is not None and (x.get("attributes") or {}).get("mop") is not None)
        rows.append([
            sheet_doc["sheet_number"], stype, str(n_total), str(n_with_key),
            str(n_with_pc), str(n_with_v), str(n_with_mca_mop),
            "", "", "" # Empty placeholders for template stats
        ])

    # Calculate template metrics
    if templates:
        t_total = len(templates)
        t_last_mod = max((t['template_last_modified'] for t in templates), default="N/A")
        t_signed_off = sum(1 for t in templates if t.get('template_status') == 'signed_off')
        
        rows.append([
            sheet_doc["sheet_number"], "template", str(t_total), "", "", "", "",
            t_last_mod, str(t_signed_off), f"{t_signed_off/t_total*100:.1f}%"
        ])
    
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_json_folder", help="path to sheet JSON folder (output of OCR)")
    ap.add_argument("output_folder", help="path to output folder (will contain JSONL files)")
    ap.add_argument("project_id", nargs='?', default=PROJECT_ID_DEFAULT, help="project identifier (e.g., veridian)")
    ap.add_argument("--templates-root", required=True, type=pathlib.Path, help="path to the root folder containing filled-in room template JSONs")
    ap.add_argument("--templates-only", action="store_true", help="skip sheet/fact processing and only generate template documents")
    args = ap.parse_args()

    in_dir = pathlib.Path(args.input_json_folder)
    out_dir = pathlib.Path(args.output_folder)
    project_id = args.project_id
    template_root = args.templates_root

    try:
        embedding_client = OpenAI()
    except Exception as exc:
        print(f"Warning: Unable to initialize OpenAI client ({exc}). Embeddings disabled.", file=sys.stderr)
        embedding_client = None

    out_dir.mkdir(parents=True, exist_ok=True)
    sheets_jsonl = out_dir / "sheets.jsonl"
    facts_jsonl  = out_dir / "facts.jsonl"
    templates_jsonl = out_dir / "templates.jsonl"
    coverage_csv = out_dir / "coverage_report.csv"

    all_sheets: List[Dict[str, Any]] = []
    all_facts:  List[Dict[str, Any]] = []
    all_templates: List[Dict[str, Any]] = []
    
    cov_rows: List[List[str]] = [[
        "sheet_number","schedule_type","rows_total","rows_with_key_id",
        "rows_with_panel_and_circuit","rows_with_voltage","rows_with_mca_mop",
        "template_last_modified", "templates_signed_off", "templates_signed_off_pct"
    ]]

    # Process Sheets and Facts unless --templates-only is set
    if not args.templates_only:
        print("Processing sheets and facts...")
        for p in sorted(in_dir.rglob("*.json")):
            raw = load_json(p)
            meta = sheet_meta(raw, project_id)
            sheet_doc = make_sheet_doc(meta, raw, embedding_client)
            facts = list(emit_facts(raw, meta, embedding_client))
            
            # Find templates related to this sheet for coverage report
            # This is a simplification; a more robust approach links them via a manifest or direct path
            sheet_templates = []
            try:
                # Assuming templates are structured like: templates_root/<discipline>/<sheet_number>/<room>.json
                sheet_template_dir = template_root / "electrical" / meta['sheet_number']
                if sheet_template_dir.exists():
                    sheet_templates.extend(list(iter_template_docs(sheet_template_dir, meta, embedding_client)))
                sheet_template_dir = template_root / "architectural" / meta['sheet_number']
                if sheet_template_dir.exists():
                    sheet_templates.extend(list(iter_template_docs(sheet_template_dir, meta, embedding_client)))
            except Exception as e:
                print(f"Error checking templates for sheet {meta['sheet_number']}: {e}", file=sys.stderr)
            
            all_sheets.append(sheet_doc)
            all_facts.extend(facts)
            all_templates.extend(sheet_templates) # Append sheet-specific templates for writing/coverage
            cov_rows.extend(coverage_rows(sheet_doc, facts, sheet_templates))
        
        write_jsonl(sheets_jsonl, all_sheets)
        write_jsonl(facts_jsonl, all_facts)
        print(f"Wrote {len(all_sheets)} sheets -> {sheets_jsonl}")
        print(f"Wrote {len(all_facts)} facts  -> {facts_jsonl}")
    else:
        print("Skipping sheet and fact processing (--templates-only set).")
        # When templates-only, we still need a meta object for iter_template_docs, use a dummy
        base_meta = sheet_meta({}, project_id)
        
    # Process Templates
    print("Processing templates...")
    if args.templates_only:
        # If templates-only, we process all templates in the root and re-create all_templates
        all_templates = list(iter_template_docs(template_root, base_meta, embedding_client))
        # Re-calculate coverage for templates-only mode (simplified: one row for all templates)
        if all_templates:
            # Group templates by sheet_number to produce meaningful coverage rows
            templates_by_sheet: Dict[str, List[Dict[str, Any]]] = {}
            for t in all_templates:
                templates_by_sheet.setdefault(t["sheet_number"], []).append(t)
            
            # Generate dummy sheet docs for coverage calculation
            for sheet_num, t_list in templates_by_sheet.items():
                dummy_sheet_doc = {"sheet_number": sheet_num} # Only need sheet_number for the report
                cov_rows.extend(coverage_rows(dummy_sheet_doc, [], t_list)) # Pass empty facts list
    
    # Write all processed templates (either full run or templates-only run)
    write_jsonl(templates_jsonl, all_templates)
    print(f"Wrote {len(all_templates)} templates -> {templates_jsonl}")


    # Write Coverage Report
    with coverage_csv.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(cov_rows)
    print(f"Wrote coverage           -> {coverage_csv}")

if __name__ == "__main__":
    main()
```

-----

## 6\) `tools/schedule_postpass/parsers.py`

```python
from typing import Dict, Any, List

# Note: This is an incomplete view of parsers.py. 
# It assumes the two new functions required by transform.py are included.

def classify_schedule_block(block: Dict[str, Any]) -> str:
    """
    Map your extractor's block metadata to our schedule_type.
    Adjust the heuristics to your JSON (name/type keys).
    """
    t = (block.get("type") or "").lower()
    n = (block.get("name") or "").lower()
    s = (block.get("subtype") or "").lower()

    hay = " ".join([t, n, s])

    if "panel" in hay and "schedule" in hay: return "panel"
    if "unit" in hay and "schedule" in hay:  return "unit_plan"
    if "lighting" in hay and "schedule" in hay: return "lighting_fixture"

    if ("electrical equipment" in hay or "single line" in hay) and "schedule" in hay:
        return "elec_equipment"
    if ("mechanical" in hay or "rtu" in hay or "ahu" in hay or "vfd" in hay) and "schedule" in hay:
        return "mech_equipment"
    if ("plumbing" in hay or "ejector" in hay or "water heater" in hay or "wh" in hay) and "schedule" in hay:
        return "plumb_equipment"

    if ("wall" in hay or "partition" in hay) and "schedule" in hay: return "wall_partition"
    if "door" in hay and "schedule" in hay: return "door"
    if "ceiling" in hay and "schedule" in hay: return "ceiling"
    if "finish" in hay and "schedule" in hay: return "finish"
    return ""

def _get(row: Dict[str, Any], *keys, default=None):
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return default

def _parse_float(x):
    if x is None: return None
    try:
        s = str(x).lower().replace(",", "").replace("in", "").replace("\"", "").strip()
        return float(s)
    except: return None

def extract_key(stype: str, row: Dict[str, Any]) -> Dict[str, Any]:
    if stype == "panel":
        panel = _get(row,"panel","panel_name","board")
        ckt   = _get(row,"circuit","ckt","cct","circuit_number")
        if panel and ckt: return {"panel": str(panel).strip(), "circuit": str(ckt).strip()}
        return {}

    if stype == "unit_plan":
        unit = _get(row,"unit","unit_id","room","space")
        tag  = _get(row,"tag","device","appliance","equipment")
        if unit and tag: return {"unit": str(unit).strip(), "tag": str(tag).strip()}
        return {}

    if stype in ("elec_equipment", "mech_equipment","plumb_equipment","lighting_fixture"):
        tag = _get(row,"tag","equipment_tag","name","fixture_type","type","mark")
        return {"tag": str(tag).strip()} if tag else {}

    if stype == "wall_partition":
        wt = _get(row,"wall_type","partition_type","type")
        return {"wall_type": str(wt).strip()} if wt else {}

    if stype == "door":
        dn = _get(row,"door_number","mark","door","id")
        return {"door_number": str(dn).strip()} if dn else {}

    if stype == "ceiling":
        ct = _get(row,"ceiling_type","type")
        return {"ceiling_type": str(ct).strip()} if ct else {}

    if stype == "finish":
        # some finish schedules are by space/room
        space = _get(row,"space","room","area","name")
        return {"tag": str(space).strip()} if space else {}

    return {}

def extract_attributes(stype: str, row: Dict[str, Any]) -> Dict[str, Any]:
    a: Dict[str, Any] = {}
    
    # --- Universal ---
    a["description"]= _get(row,"description","desc","notes","load")

    # --- Electrical (Panel, Unit, Equip) ---
    a["voltage"]    = _parse_float(_get(row,"voltage","volts","v"))
    a["phase"]      = _get(row,"phase","ph")
    a["rating_a"]   = _parse_float(_get(row,"amps","amp","a","breaker","breaker_a")) # Use for panel breaker or unit plan
    a["wire"]       = _get(row,"wire","conductor")
    a["conduit"]    = _get(row,"conduit","raceway")
    a["hp"]         = _parse_float(_get(row,"hp"))
    a["kw"]         = _parse_float(_get(row,"kw"))
    a["kva"]        = _parse_float(_get(row,"kva"))
    a["mca"]        = _parse_float(_get(row,"mca"))
    a["mop"]        = _parse_float(_get(row,"mop"))
    a["fla"]        = _parse_float(_get(row,"fla"))
    a["busbar_a"]   = _parse_float(_get(row,"busbar_a"))
    a["disconnect"] = _get(row,"disconnect","disc")
    # For Unit Plans (if they list panel info)
    a["panel"]      = _get(row,"panel","panel_name")
    a["circuit"]    = _get(row,"circuit","ckt","cct")

    # --- Plumbing ---
    a["btu"]        = _parse_float(_get(row,"btu"))
    a["gpm"]        = _parse_float(_get(row,"gpm"))
    a["head"]       = _parse_float(_get(row,"head"))

    # --- Lighting ---
    a["fixture_type"] = _get(row,"fixture_type","type","mark") # Also in key, but good to have
    a["lumens"]       = _parse_float(_get(row,"lumens","lm"))
    a["lamp_type"]   = _get(row,"lamp_type","lamp")
    a["cct"]         = _get(row,"cct")
    a["cri"]         = _get(row,"cri")
    a["mounting"]    = _get(row,"mounting","mount")
    a["dimming"]     = _get(row,"dimming")

    # --- Architectural ---
    # Wall
    a["stc"]                = _parse_float(_get(row,"stc"))
    a["fire_rating"]        = _get(row,"fire_rating","fr","rating")
    a["stud_gauge"]         = _get(row,"stud_gauge","stud")
    a["layers"]             = _get(row,"layers")
    # Ceiling
    a["ceiling_height_in"]  = _parse_float(_get(row,"ceiling_height_in","height","ht"))
    a["acoustic"]           = _get(row,"acoustic","nrc")
    a["grid"]               = _get(row,"grid")
    # Finish
    a["finish_floor"]       = _get(row,"finish_floor","floor_finish")
    a["finish_wall"]        = _get(row,"finish_wall","wall_finish")
    a["finish_ceiling"]     = _get(row,"finish_ceiling","ceiling_finish")
    # Door
    a["hardware_set"]       = _get(row,"hardware_set","hw_set")
    a["size"]               = _get(row,"size")
    a["material_frame"]    = _get(row,"material_frame","material","frame")

    # --- Automatic Labels ---
    labels = []
    d = (a.get("description") or "").lower()
    if "em" in d or "emergency" in d: labels.append("EM")
    if "gfci" in d: labels.append("GFCI")
    if "wp" in d or "weatherproof" in d: labels.append("WP")
    if "spare" in d:
        labels.append("Spare")
        a["is_spare"] = True
    if "space" in d:
        labels.append("Space")
        a["is_space"] = True

    if labels: a["_labels"] = list(set(labels)) # Use set for automatic dedupe

    # clean empties
    return {k:v for k,v in a.items() if v not in (None, "", [])}

def build_summary(stype: str, key: Dict[str, Any], a: Dict[str, Any]) -> str:
    # NOTE: Summaries are intentionally simple and don't include all merged attributes.
    # The full data is in the 'attributes' field.
    try:
        if stype == "panel":
            ra = f"{int(a['rating_a'])}A" if a.get("rating_a") is not None else ""
            conduit = f", {a['conduit']}" if a.get("conduit") else ""
            return f"Panel {key.get('panel')} — Ckt {key.get('circuit')} — {a.get('description','').strip()} — {ra}{conduit}".strip(" —,")
        if stype == "unit_plan":
            volt = f"{int(a['voltage'])}V" if a.get("voltage") is not None else ""
            ph = f"/{a['phase']}φ" if a.get("phase") else ""
            ra = f", {int(a['rating_a'])}A" if a.get("rating_a") is not None else ""
            return f"Unit {key.get('unit')} — {key.get('tag')} — {volt}{ph}{ra}".strip(" —,")
        if stype == "mech_equipment":
            volt = f"{int(a['voltage'])}V" if a.get("voltage") is not None else ""
            ph = f"/{a['phase']}φ" if a.get("phase") else ""
            hp = f", {a['hp']}HP" if a.get("hp") is not None else ""
            kw = f" ({a['kw']}kW)" if a.get("kw") is not None else ""
            mc = f", MCA {a['mca']}" if a.get("mca") is not None else ""
            mo = f"/MOP {a['mop']}" if a.get("mop") is not None else ""
            return f"{key.get('tag')} — {volt}{ph}{hp}{kw}{mc}{mo}".strip(" —,")
            # Lighting fixture
        if stype == "lighting_fixture":
            volt = f"{int(a['voltage'])}V" if a.get("voltage") is not None else ""
            lum  = f", {int(a['lumens'])} lm" if a.get("lumens") is not None else ""
            return f"{key.get('tag') or a.get('fixture_type','Fixture')} — {volt}{lum}".strip(" —,")
        if stype == "wall_partition":
            fr = a.get("fire_rating","")
            stc = f", STC {int(a['stc'])}" if a.get("stc") is not None else ""
            return f"{key.get('wall_type')} — {fr}{stc}".strip(" —,")
        if stype == "door":
            hs = f", {a['hardware_set']}" if a.get("hardware_set") else ""
            fr = f", rating {a['fire_rating']}" if a.get("fire_rating") else ""
            return f"Door {key.get('door_number')}{hs}{fr}".strip(" —,")
        if stype == "ceiling":
            ht = f"{a['ceiling_height_in']} in" if a.get("ceiling_height_in") is not None else ""
            return f"{key.get('ceiling_type')} — {ht}".strip(" —,")
        if stype == "finish":
            return f"{key.get('tag','Space')} — floor {a.get('finish_floor','')}".strip(" —,")
        return "row"
    except Exception:
        return "row"


# --- New Template Functions ---

def build_template_summary(template_type: str, raw: Dict[str, Any]) -> str:
    """Creates a short, human-readable summary for a template doc's 'content' field.
    Handles comprehensive template structure with all systems."""
    room_id = raw.get("room_id") or raw.get("room_name", "Space")
    status = raw.get("template_status", "in_progress")
    
    if template_type == "electrical":
        parts = []
        
        # Circuits
        circuits = raw.get("circuits", {})
        lighting = circuits.get("lighting", [])
        if lighting:
            parts.append(f"Lighting: {', '.join(lighting[:3])}{'...' if len(lighting) > 3 else ''}")
        
        # Outlets
        outlets = raw.get("outlets", {})
        total = sum([outlets.get("regular_outlets", 0), outlets.get("controlled_outlets", 0),
                     outlets.get("gfci_outlets", 0), outlets.get("usb_outlets", 0)])
        if total > 0:
            parts.append(f"{total} outlets")
        
        # Fire Alarm
        fa = raw.get("fire_alarm", {})
        fa_devices = sum([fa.get(k, {}).get("count", 0) for k in ["smoke_detectors", "heat_detectors", "pull_stations", "horn_strobes"]])
        if fa_devices > 0:
            parts.append(f"{fa_devices} FA devices")
        
        # Data/Telecom
        dt = raw.get("data_telecom", {})
        data_count = dt.get("data_outlets", 0)
        if data_count > 0:
            parts.append(f"{data_count} data")
        
        # Special Systems
        if raw.get("nurse_call", {}).get("stations", {}).get("count", 0) > 0:
            parts.append("nurse call")
        if raw.get("medical_gas", {}).get("oxygen", {}).get("count", 0) > 0:
            parts.append("medical gas")
        if raw.get("security", {}).get("cameras", {}).get("count", 0) > 0:
            parts.append("security")
        
        summary = f"{room_id} Electrical — " + ", ".join(parts) if parts else f"{room_id} Electrical (empty)"
        return f"{summary} ({status})"
    
    if template_type == "architectural":
        parts = []
        
        # Dimensions
        dims = raw.get("dimensions", "")
        ceiling = raw.get("ceiling_height", "")
        if dims:
            parts.append(f"Dims: {dims}")
        if ceiling:
            parts.append(f"Ceiling: {ceiling}")
        
        # Finishes
        finishes = raw.get("finishes", {})
        floor_mat = finishes.get("floor", {}).get("material", "")
        if floor_mat:
            parts.append(f"Floor: {floor_mat}")
        
        # Doors
        doors = raw.get("doors", {})
        door_count = doors.get("count", 0)
        if door_count > 0:
            parts.append(f"{door_count} doors")
        
        # Special rooms
        special = raw.get("special_rooms", {})
        if special.get("clean_room", {}).get("classification"):
            parts.append("clean room")
        if special.get("lab", {}).get("fume_hood"):
            parts.append("lab")
        if special.get("operating_room", {}).get("or_number"):
            parts.append("OR")
        
        # ADA
        if raw.get("accessibility", {}).get("ada_required"):
            parts.append("ADA")
        
        summary = f"{room_id} Architectural — " + ", ".join(parts) if parts else f"{room_id} Architectural (empty)"
        return f"{summary} ({status})"
        
    return f"{room_id} Template ({template_type}) - Status: {status}"

def derive_template_tags(raw: Dict[str, Any]) -> List[str]:
    """Derives automatic tags from the comprehensive template payload."""
    tags = []
    
    # Basic Electrical
    circuits = raw.get("circuits", {})
    if circuits.get("lighting"): tags.append("lighting")
    if circuits.get("power"): tags.append("power")
    if circuits.get("emergency"): tags.append("emergency")
    if circuits.get("critical"): tags.append("critical")
    if circuits.get("ups"): tags.append("ups")
    
    outlets = raw.get("outlets", {})
    if outlets.get("regular_outlets", 0) > 0 or outlets.get("controlled_outlets", 0) > 0:
        tags.append("outlets")
    if outlets.get("gfci_outlets", 0) > 0: tags.append("gfci")
    if outlets.get("hospital_grade", 0) > 0: tags.append("hospital_grade")
    if outlets.get("red_outlets", 0) > 0: tags.append("emergency_power")
    
    if raw.get("mechanical_equipment"): tags.append("mechanical")
    if raw.get("appliances"): tags.append("appliances")
    
    # Fire Alarm
    fa = raw.get("fire_alarm", {})
    if any([fa.get(k, {}).get("count", 0) > 0 for k in ["smoke_detectors", "heat_detectors", "pull_stations", "horn_strobes"]]):
        tags.append("fire_alarm")
    
    # Data/Telecom
    dt = raw.get("data_telecom", {})
    if dt.get("data_outlets", 0) > 0: tags.append("data")
    if dt.get("wireless_ap"): tags.append("wireless")
    
    # Security
    sec = raw.get("security", {})
    if sec.get("cameras", {}).get("count", 0) > 0: tags.append("security")
    if sec.get("card_readers", {}).get("count", 0) > 0: tags.append("access_control")
    
    # AV
    av = raw.get("audiovisual", {})
    if av.get("displays", {}).get("count", 0) > 0 or av.get("projectors", {}).get("count", 0) > 0:
        tags.append("audiovisual")
    
    # Healthcare
    if raw.get("nurse_call", {}).get("stations", {}).get("count", 0) > 0:
        tags.append("nurse_call")
    if raw.get("medical_gas", {}).get("oxygen", {}).get("count", 0) > 0:
        tags.append("medical_gas")
    
    # Lab/Special
    lab = raw.get("lab_systems", {})
    if lab.get("fume_hood") or lab.get("biosafety_cabinet"):
        tags.append("lab")
    
    # Data Center
    dc = raw.get("data_center", {})
    if dc.get("rack_count", 0) > 0:
        tags.append("data_center")
    
    # Kitchen
    kitchen = raw.get("kitchen_systems", {})
    if kitchen.get("hood_suppression"):
        tags.append("food_service")
    
    # Architectural
    if raw.get("walls"): tags.append("walls")
    if raw.get("ceiling_height"): tags.append("ceiling")
    if raw.get("dimensions"): tags.append("dimensions")
    
    finishes = raw.get("finishes", {})
    if finishes: tags.append("finishes")
    
    doors = raw.get("doors", {})
    if doors.get("count", 0) > 0: tags.append("doors")
    if doors.get("fire_rated"): tags.append("fire_rated")
    
    # Code/Compliance
    if raw.get("accessibility", {}).get("ada_required"):
        tags.append("ada")
    if raw.get("fire_life_safety", {}).get("fire_rating_required"):
        tags.append("fire_rated")
    
    # Special Room Types
    special = raw.get("special_rooms", {})
    if special.get("clean_room", {}).get("classification"):
        tags.append("clean_room")
    if special.get("lab", {}).get("fume_hood"):
        tags.append("lab")
    if special.get("operating_room", {}).get("or_number"):
        tags.append("operating_room")
    if special.get("data_center", {}).get("raised_floor"):
        tags.append("data_center")
    
    # Status
    if raw.get("template_status") == "signed_off": tags.append("signed_off")
    
    # Field Issues
    if raw.get("discrepancies"): tags.append("has_discrepancies")
    
    return list(set([t.lower() for t in tags]))  # Dedupe with set
```

-----

## 7\) `tools/schedule_postpass/synonyms.seed.json`

```json
{
  "name": "project-synonyms",
  "synonyms": [
    { "from": ["first floor","1st","l1"], "to": "level 1" },
    { "from": ["second floor","2nd","l2"], "to": "level 2" },
    { "from": ["third floor","3rd","l3"], "to": "level 3" },
    { "from": ["fourth floor","4th","l4"], "to": "level 4" },
    { "from": ["fifth floor","5th","l5"], "to": "level 5" },
    { "from": ["sixth floor","6th","l6"], "to": "level 6" },
    { "from": ["seventh floor","7th","l7"], "to": "level 7" },
    { "from": ["eighth floor","8th","l8"], "to": "level 8" },
    { "from": ["ninth floor","9th","l9"], "to": "level 9" },
    { "from": ["tenth floor","10th","l10"], "to": "level 10" },
    { "from": ["roof level","r"], "to": "roof" },

    { "from": ["partition types","partition type","wall type"], "to": "wall types" },
    { "from": ["reflected ceiling plan","rcp"], "to": "ceiling plan" },
    
    { "from": ["elec room","electrical room","elec","er"], "to": "electrical room" },
    { "from": ["mdf","main distribution frame"], "to": "mdf" },
    { "from": ["idf","intermediate distribution frame"], "to": "idf" },
    
    { "from": ["swbd","switchboard"], "to": "switchboard" },
    { "from": ["xfmr","transformer"], "to": "transformer" },
    { "from": ["bus duct"], "to": "busway" },
    { "from": ["wire gutter"], "to": "gutter" },

    { "from": ["rtu","rooftop unit"], "to": "rtu" },
    { "from": ["ahu","air handling unit"], "to": "ahu" },
    { "from": ["ef","exhaust fan"], "to": "ef" },
    { "from": ["vfd","variable frequency drive"], "to": "vfd" },
    { "from": ["vav"], "to": "variable air volume" },
    { "from": ["fcu"], "to": "fan coil unit" },
    { "from": ["mau"], "to": "makeup air unit" },
    { "from": ["doas"], "to": "dedicated outdoor air system" },
    { "from": ["erv"], "to": "energy recovery ventilator" },

    { "from": ["wp gfci","weatherproof gfci"], "to": "gfci" },
    { "from": ["gfci","gfi"], "to": "gfci" },
    { "from": ["afci"], "to": "arc fault" },
    { "from": ["wp"], "to": "weatherproof" },
    { "from": ["ig"], "to": "isolated ground" },

    { "from": ["dw"], "to": "dishwasher" },
    { "from": ["wh"], "to": "water heater" },
    { "from": ["ewh"], "to": "electric water heater" },
    { "from": ["rng"], "to": "range" },
    { "from": ["dr"], "to": "dryer" },
    { "from": ["hw"], "to": "hot water" },
    { "from": ["cw"], "to": "cold water" },
    { "from": ["hwr"], "to": "hot water return" },
    { "from": ["wc"], "to": "water closet" },
    { "from": ["prv"], "to": "pressure reducing valve" },

    { "from": ["ss"], "to": "stainless steel" },
    { "from": ["pt"], "to": "paint" },
    { "from": ["ct"], "to": "ceramic tile" },
    { "from": ["aff"], "to": "above finish floor" },
    { "from": ["nts"], "to": "not to scale" },
    { "from": ["typ"], "to": "typical" },
    { "from": ["correlated color temperature"], "to": "cct" },
    { "from": ["color rendering index"], "to": "cri" },
    
    { "from": ["em","emerg"], "to": "emergency" },
    { "from": ["or"], "to": "operating room" },
    { "from": ["er"], "to": "emergency room" },
    { "from": ["ma"], "to": "medical air" },
    { "from": ["wagd"], "to": "waste anesthesia gas disposal" },
    { "from": ["crac"], "to": "computer room air conditioner" },
    { "from": ["crah"], "to": "computer room air handler" },
    { "from": ["pdu"], "to": "power distribution unit" },
    { "from": ["epo"], "to": "emergency power off" },
    { "from": ["evse"], "to": "electric vehicle charging" },
    { "from": ["hvls"], "to": "high volume low speed fan" },
    { "from": ["ex sign","ex"], "to": "exit sign" }
  ]
}
```

-----

## 8\) `tools/schedule_postpass/upsert_index.py`

Pass the new `templates.jsonl` file to the uploader so templates land in the same index. We also add a `--mode incremental` switch so foreman-only updates can skip the destructive index recreate and automatically push the synonym map from `synonyms.seed.json`.

```python
#!/usr/bin/env python3
import os, json, argparse, pathlib, requests

AZURE_SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]      # e.g., https://<service>.search.windows.net
AZURE_SEARCH_API_KEY = os.environ["AZURE_SEARCH_API_KEY"]
INDEX_NAME = os.environ.get("INDEX_NAME","drawings_unified")

def create_index(schema_path: pathlib.Path):
    url = f"{AZURE_SEARCH_ENDPOINT}/indexes/{INDEX_NAME}?api-version=2024-07-01"
    headers = {"Content-Type":"application/json","api-key":AZURE_SEARCH_API_KEY}
    
    # Read schema from the .json file
    try:
        schema = json.loads(schema_path.read_text())
    except FileNotFoundError:
        print(f"Error: Schema file not found at {schema_path}")
        raise
    except json.JSONDecodeError:
        print(f"Error: Schema file {schema_path} is not valid JSON.")
        raise
        
    # create or replace
    print(f"Attempting to create/update index '{INDEX_NAME}'...")
    r = requests.put(url, headers=headers, data=json.dumps(schema))
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Index create failed: {r.status_code} {r.text}")
    print("Index created/replaced.")

def create_synonym_map(synonyms_path: pathlib.Path):
    url = f"{AZURE_SEARCH_ENDPOINT}/synonymmaps/project-synonyms?api-version=2024-07-01"
    headers = {"Content-Type":"application/json","api-key":AZURE_SEARCH_API_KEY}
    try:
        raw_payload = json.loads(synonyms_path.read_text())
    except FileNotFoundError:
        raise FileNotFoundError(f"Synonym file not found at {synonyms_path}")
    except json.JSONDecodeError:
        raise ValueError(f"Synonym file {synonyms_path} is not valid JSON.")

    if isinstance(raw_payload, dict) and "synonyms" in raw_payload and isinstance(raw_payload["synonyms"], list):
        lines = []
        for entry in raw_payload["synonyms"]:
            if not isinstance(entry, dict):
                continue
            from_terms = entry.get("from") or []
            to_term = entry.get("to")
            if from_terms and to_term:
                lines.append(f"{', '.join(from_terms)} => {to_term}")
        payload = {
            "name": "project-synonyms",
            "format": "solr",
            "synonyms": "\n".join(lines)
        }
    else:
        payload = raw_payload
        payload.setdefault("name", "project-synonyms")
        payload.setdefault("format", "solr")

    print("Creating/updating synonym map 'project-synonyms'...")
    r = requests.put(url, headers=headers, data=json.dumps(payload))
    if r.status_code == 409:
        headers["If-Match"] = "*"
        r = requests.put(url, headers=headers, data=json.dumps(payload))
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Synonym map create failed: {r.status_code} {r.text}")
    print("Synonym map ready.")

def upload_jsonl(jsonl_path: pathlib.Path, batch_size=1000):
    if not jsonl_path.exists():
        print(f"Skipping upload: {jsonl_path.name} not found.")
        return

    url = f"{AZURE_SEARCH_ENDPOINT}/indexes/{INDEX_NAME}/docs/index?api-version=2024-07-01"
    headers = {"Content-Type":"application/json","api-key":AZURE_SEARCH_API_KEY}
    batch = []
    count = 0
    print(f"Uploading {jsonl_path.name}...")
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            doc = json.loads(line)
            # We already popped raw_json in transform.py, but as a safeguard:
            doc.pop("raw_json", None) 
            batch.append({"@search.action": "mergeOrUpload", **doc})
            count += 1
            if len(batch) >= batch_size:
                r = requests.post(url, headers=headers, data=json.dumps({"value": batch}))
                if r.status_code not in (200, 201):
                    raise RuntimeError(f"Upload error: {r.status_code} {r.text}")
                batch = []
    if batch:
        r = requests.post(url, headers=headers, data=json.dumps({"value": batch}))
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Upload error: {r.status_code} {r.text}")
    print(f"Uploaded {count} documents from {jsonl_path.name}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", required=True, help="path to unified_index.schema.json")
    ap.add_argument("--sheets", required=False, default="", help="path to sheets.jsonl")
    ap.add_argument("--facts", required=False, default="", help="path to facts.jsonl")
    ap.add_argument("--templates", required=False, default="", help="path to templates.jsonl (new input)")
    ap.add_argument("--synonyms", required=False, default="", help="path to synonyms.seed.json")
    ap.add_argument("--mode", default="full", choices=["full", "incremental"], help="upload mode: 'full' (recreate index) or 'incremental' (merge/upload only)")
    args = ap.parse_args()

    if args.mode == "full":
        if args.synonyms:
            create_synonym_map(pathlib.Path(args.synonyms))
        create_index(pathlib.Path(args.schema))
    else:
        print(f"Incremental mode selected: Skipping index creation/replacement.")

    if args.sheets:
        upload_jsonl(pathlib.Path(args.sheets))
    if args.facts:
        upload_jsonl(pathlib.Path(args.facts))
    if args.templates: # New template upload
        upload_jsonl(pathlib.Path(args.templates))
        
    print("All done.")

if __name__ == "__main__":
    main()
```

-----

## 9\) `tools/schedule_postpass/query_playbook.py`

```python
#!/usr/bin/env python3
import os, json, requests, sys
from typing import Optional, List
from openai import OpenAI

# --- Config ---
ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
API_KEY  = os.environ["AZURE_SEARCH_API_KEY"]
INDEX    = os.environ.get("INDEX_NAME","drawings_unified")
API_VER  = "2024-07-01"
# --- End Config ---

try:
    EMBEDDING_CLIENT = OpenAI()
except Exception as exc:
    print(f"Warning: OpenAI client unavailable ({exc}). Vector queries disabled.", file=sys.stderr)
    EMBEDDING_CLIENT = None

def post_search(body: dict) -> dict:
    """Helper to post a search query and handle errors."""
    url = f"{ENDPOINT}/indexes/{INDEX}/docs/search?api-version={API_VER}"
    headers = {"Content-Type":"application/json","api-key":API_KEY}
    try:
        r = requests.post(url, headers=headers, data=json.dumps(body))
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        print(f"Search request failed: {e}", file=sys.stderr)
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}", file=sys.stderr)
        return {"value": []} # Return empty on failure

def generate_query_embedding(text: str) -> Optional[List[float]]:
    """Generate an embedding for hybrid search."""
    if not EMBEDDING_CLIENT or not text or not text.strip():
        return None
    try:
        resp = EMBEDDING_CLIENT.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return resp.data[0].embedding
    except Exception as exc:
        print(f"Embedding generation failed: {exc}", file=sys.stderr)
        return None

def unified_search(search_text, search_filter=None, top=25):
    """
    Searches facts first, then falls back to templates, then sheets if no facts are found.
    
    Args:
        search_text: The user's query string.
        search_filter: The OData filter to apply for the initial search.
                     Defaults to searching all doc_types.
    """
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
        "facet": ["discipline","schedule_type","levels","template_status","doc_type","template_tags"],
        "select": "id,doc_type,project,sheet_number,sheet_title,discipline,schedule_type,key,attributes,labels,revision,source_file,content,template_type,room_id,template_status"
    }
    query_vector = generate_query_embedding(search_text)
    if query_vector:
        base_body["vectorQueries"] = [{
            "vector": query_vector,
            "kNearestNeighborsCount": 50,
            "fields": "content_vector"
        }]

    # Order of search: 
    # 1. Facts (most granular)
    # 2. Templates (human-in-the-loop truth)
    # 3. Sheets (fallback)
    
    # 1. --- Try Facts First ---
    fact_filter = search_filter if search_filter else "doc_type eq 'fact'"
    fact_body = dict(base_body)
    fact_body["filter"] = fact_filter
    fact_res = post_search(fact_body)
    
    if fact_res.get("value"):
        print(f"--- Found {len(fact_res['value'])} matching FACTS ---", file=sys.stderr)
        return fact_res

    # 2. --- Fallback to Templates ---
    template_filter = search_filter if search_filter else "doc_type eq 'template'"
    template_body = dict(base_body)
    template_body["filter"] = template_filter
    template_res = post_search(template_body)
    
    if template_res.get("value"):
        print(f"--- No facts found, falling back to {len(template_res['value'])} TEMPLATES ---", file=sys.stderr)
        return template_res

    # 3. --- Fallback to Sheets ---
    # Only fall back if the fact filter was the default doc_type eq 'fact'.
    # If the user *specifically* asked for, e.g., panel facts, don't show sheets.
    if search_filter is None or search_filter == "doc_type eq 'fact'":
        print("--- No facts or templates found, falling back to SHEETS ---", file=sys.stderr)
        sheet_body = dict(base_body)
        sheet_body["filter"] = "doc_type eq 'sheet'"
        sheet_res = post_search(sheet_body)
        return sheet_res
    
    # 4. --- Return Empty (if specific filter yielded no results) ---
    print("--- No specific results found, not falling back. ---", file=sys.stderr)
    return fact_res # Return the empty response


def show(title, res):
    """Pretty-print search results."""
    print(f"\n=== {title} ===")
    count = res.get("@odata.count", len(res.get("value", [])))
    print(f"Total results: {count}")
    
    for i, hit in enumerate(res.get("value", []), 1):
        doc = hit
        score = hit.get("@search.score", 0.0)
        
        # Display logic based on doc_type
        doc_type = doc.get('doc_type')
        print(f"\n{i:2d}. [Score: {score:.2f}] [{doc_type}] {doc.get('content')}")
        
        if doc_type == "fact":
            print(f"    -> {doc.get('schedule_type')} | key={doc.get('key')} | sheet={doc.get('sheet_number')}")
        elif doc_type == "template":
             print(f"    -> {doc.get('template_type')} | room={doc.get('room_id')} | status={doc.get('template_status')} | sheet={doc.get('sheet_number')}")
        else: # sheet
            print(f"    -> sheet={doc.get('sheet_number')} | title={doc.get('sheet_title')}")

if __name__ == "__main__":
    print("--- Running query playbook (Developer Sanity Check) ---")
    print("--- NOTE: This script demonstrates the 'facts-first' logic. ---")
    print("--- Your production Azure Function will handle the real queries. ---")
    
    # Example 1: General search, facts-first
    res1 = unified_search("dishwasher A4")
    show("Dishwasher in Unit A4 (Facts-first)", res1)

    # Example 2: Search for a signed-off template (will skip facts)
    # NOTE: This assumes your test data includes a signed-off template
    # Example content would be: "A4 Electrical — Lighting: L47, L48, Outlets: 8 (2 controlled), Fixtures: 4, Equipment: DW, Range (signed_off)"
    template_filter = "doc_type eq 'template' and template_status eq 'signed_off'"
    res2 = unified_search("Unit A4 Kitchen", search_filter=template_filter, top=50)
    show("Signed-off templates in Unit A4 (Templates-only)", res2)

    # Example 3: Search *specifically* for panel facts (will not fall back to templates/sheets)
    panel_filter = "doc_type eq 'fact' and schedule_type eq 'panel' and key/panel eq 'S2'"
    res3 = unified_search("", search_filter=panel_filter, top=200) # Empty search, filter only
    show("Panel S2 schedule (Facts-only, no fallback)", res3)

    # Example 4: Search that might fall back to sheets
    res4 = unified_search("main riser diagram")
    show("Main Riser Diagram (May fall back to sheets)", res4)
```

-----

## 10\) `tools/schedule_postpass/tests/test_postpass.py`

```python
import json, pathlib, subprocess, sys

# Simple import for local testing, adjust `..` if structured as a package
try:
    from .. import transform
except ImportError:
    # This allows running pytest from the repo root
    sys.path.append(str(pathblib.Path(__file__).parent.parent.parent))
    from tools.schedule_postpass import transform

# Dummy template content for testing (matches comprehensive e_rooms_template.json structure)
SAMPLE_TEMPLATE_ELEC = {
    "sheet_number": "E2.03",
    "room_id": "A4",
    "room_name": "Unit A4 Kitchen",
    "levels": ["Level 2"],
    "occupancy_type": "kitchen",
    "template_status": "signed_off",
    "template_author": "jfernandez",
    "template_last_modified": "2025-05-01T10:00:00Z",
    "circuits": {
        "lighting": ["L47", "L48"],
        "power": ["P12"],
        "emergency": []
    },
    "light_fixtures": {
        "fixture_ids": ["A", "B"],
        "fixture_count": {"A": 2, "B": 2},
        "fixture_notes": "Type A = LED troffer, B = pendant"
    },
    "outlets": {
        "regular_outlets": 6,
        "controlled_outlets": 2,
        "gfci_outlets": 2,
        "usb_outlets": 0
    },
    "switches": {
        "count": 2,
        "type": "dimmer",
        "model": "Lutron",
        "dimming": "0-10V"
    },
    "appliances": ["DW", "Range"],
    "fire_alarm": {
        "smoke_detectors": {"count": 1, "type": "photoelectric", "locations": ["ceiling"]},
        "horn_strobes": {"count": 0}
    },
    "data_telecom": {
        "data_outlets": 2,
        "wireless_ap": False
    },
    "discrepancies": [],
    "field_notes": ""
}

def test_transform_runs(tmp_path: pathlib.Path):
    # This sample data includes fields that will be parsed by the *merged* parser
    sample_sheet = {
        "project_name":"Veridian Block 1",
        "sheet_number":"E2.03",
        "sheet_title":"UNIT PLAN SCHEDULE",
        "discipline":"electrical",
        "revision":"IFC 2025-04-18",
        "revision_date":"2025-04-18",
        "source_file":"electrical/E2.03.pdf",
        "content":"Full sheet text content...",
        "blocks":[
          {
            "type":"unit schedule",
            "name":"UNIT PLAN SCHEDULE",
            "rows":[
             {"unit":"A4","device":"Dishwasher","panel":"S2","circuit":"47","voltage":"120","phase":"1","amps":"20", "description": "DW GFCI"},
             {"unit":"A4","device":"Range","panel":"S2","circuit":"49,51","voltage":"120/208","phase":"1","amps":"50", "description": "RNG"}
            ]
          },
          {
            "type":"panel schedule",
            "name":"PANEL S2",
            "rows":[
                {"panel":"S2","circuit":"47","load":"Dishwasher","amps":"20","voltage":"120"},
                {"panel":"S2","circuit":"48","load":"EM LIGHTS","amps":"20","voltage":"120"}
            ]
          }
        ]
    }
    in_dir = tmp_path/"in"; out_dir = tmp_path/"out"; templates_dir = tmp_path/"templates_root"
    in_dir.mkdir(); out_dir.mkdir(); templates_dir.mkdir()
    
    # Create template file
    templates_dir.joinpath("electrical/E2.03").mkdir(parents=True)
    templates_dir.joinpath("electrical/E2.03/A4.json").write_text(json.dumps(SAMPLE_TEMPLATE_ELEC))
    
    (in_dir/"E2.03.json").write_text(json.dumps(sample_sheet))
    
    # Get path to the transform.py script
    script_path = pathlib.Path(transform.__file__)
    
    # --- Run 1: Full run (sheets, facts, templates) ---
    ret = subprocess.run(
        [sys.executable, str(script_path), str(in_dir), str(out_dir), "veridian", "--templates-root", str(templates_dir)],
        capture_output=True, text=True, check=True
    )
    
    assert ret.returncode == 0
    
    # Check Facts
    facts_path = out_dir / "facts.jsonl"
    assert facts_path.exists()
    facts = [json.loads(line) for line in facts_path.read_text().strip().splitlines()]
    assert len(facts) == 4 # 2 from unit plan, 2 from panel schedule
    
    # Check Templates
    templates_path = out_dir / "templates.jsonl"
    assert templates_path.exists()
    templates = [json.loads(line) for line in templates_path.read_text().strip().splitlines()]
    assert len(templates) == 1
    
    unit_fact = next(f for f in facts if f["schedule_type"] == "unit_plan" and f["key"]["tag"] == "Dishwasher")
    assert unit_fact["attributes"]["panel"] == "S2" 

    template_doc = templates[0]
    assert template_doc["doc_type"] == "template"
    assert template_doc["room_id"] == "A4"
    assert "signed_off" in template_doc["template_tags"] # Check derived tag
    assert "lighting" in template_doc["template_tags"] # Check lighting tag derived from circuits
    assert "outlets" in template_doc["template_tags"] # Check outlets tag
    assert "gfci" in template_doc["template_tags"] # Check GFCI tag from outlets
    assert "appliances" in template_doc["template_tags"] # Check appliances tag
    assert "fire_alarm" in template_doc["template_tags"] # Check fire alarm tag
    assert "data" in template_doc["template_tags"] # Check data tag
    assert template_doc["template_status"] == "signed_off"
    assert template_doc["template_payload"].startswith('{"sheet_number":') # Check payload exists
    assert "L47" in template_doc["content"] # Check summary contains lighting circuit

    # Check Coverage Report
    coverage_path = out_dir / "coverage_report.csv"
    csv_content = coverage_path.read_text()
    assert "template_last_modified" in csv_content # Check new header
    assert "E2.03,unit_plan" in csv_content
    assert "E2.03,template,1" in csv_content # One template found for E2.03

    # --- Run 2: Templates-only run (simulate foreman update) ---
    # Change template status
    updated_template = SAMPLE_TEMPLATE_ELEC.copy()
    updated_template["template_status"] = "in_progress"
    templates_dir.joinpath("electrical/E2.03/A4.json").write_text(json.dumps(updated_template))
    
    ret_inc = subprocess.run(
        [sys.executable, str(script_path), str(in_dir), str(out_dir), "veridian", "--templates-root", str(templates_dir), "--templates-only"],
        capture_output=True, text=True, check=True
    )
    
    assert ret_inc.returncode == 0
    
    # Check that templates.jsonl was updated
    templates_inc = [json.loads(line) for line in templates_path.read_text().strip().splitlines()]
    assert len(templates_inc) == 1
    assert templates_inc[0]["template_status"] == "in_progress"
    
    # Check that sheets.jsonl and facts.jsonl were NOT touched (by checking file size/date)
    # The simplest check is to ensure the files still exist and the facts file is NOT empty
    assert (out_dir / "sheets.jsonl").exists()
    assert len(facts) > 0 
```

-----

## 11\) `tools/schedule_postpass/README.md` (Updated)

````md
# Schedule Post-Pass (Unified Index)

## TL;DR
- Keep **SHEET** docs as-is (your current per-sheet JSON + `content`).
- Emit one **FACT** doc per **schedule row** into the **same index** (`doc_type="fact"`).
- Emit one **TEMPLATE** doc per room using the `templates/e_rooms_template.json` + `templates/a_rooms_template.json` scaffolds (foreman editable, `doc_type="template"`).
- Index name: `drawings_unified`.

## 1) Run the transformer
Templates live under `/path/to/templates_run` (e.g., `templates_run/electrical/E2.03/A4.json`); keep copying the repo defaults forward and extend them as needed.

```bash
python tools/schedule_postpass/transform.py \
  /path/to/sheet_json_folder \
  /tmp/out \
  veridian \
  --templates-root /path/to/templates_run
````

Generates embeddings for vector search using OpenAI `text-embedding-3-small`.
Embedding cost: ~$0.78 per 12-story building (one-time, updates only changed docs).

To update *only* foreman-edited room templates (skipping sheet/fact reprocessing):

```bash
python tools/schedule_postpass/transform.py \
  /path/to/sheet_json_folder \
  /tmp/out \
  veridian \
  --templates-root /path/to/templates_run \
  --templates-only
```

Outputs:

  * `/tmp/out/sheets.jsonl`
  * `/tmp/out/facts.jsonl`
  * `/tmp/out/templates.jsonl`
  * `/tmp/out/coverage_report.csv` (Now with expanded metrics + template coverage)

## 2\) Create the index & upload docs

Set env vars:

```
export AZURE_SEARCH_ENDPOINT="https://<service>.search.windows.net"
export AZURE_SEARCH_API_KEY="<key>"
export INDEX_NAME="drawings_unified"
```

Create + upload (Full rebuild):

```bash
python tools/schedule_postpass/upsert_index.py \
  --schema ./tools/schedule_postpass/unified_index.schema.json \
  --synonyms ./tools/schedule_postpass/synonyms.seed.json \
  --sheets /tmp/out/sheets.jsonl \
  --facts  /tmp/out/facts.jsonl \
  --templates /tmp/out/templates.jsonl \
  --mode full
```

Create + upload (Incremental template sync):

```bash
python tools/schedule_postpass/upsert_index.py \
  --schema ./tools/schedule_postpass/unified_index.schema.json \
  --templates /tmp/out/templates.jsonl \
  --mode incremental
```

> The `unified_index.schema.json` file is now included in this folder.
>
> When a foreman tweaks a single room, rerun `transform.py --templates-only ...` to refresh `/tmp/out/templates.jsonl`, then call the uploader with `--mode incremental` so you don’t recycle the whole index mid-day.

## 3\) Attach synonyms

> Passing `--synonyms ./tools/schedule_postpass/synonyms.seed.json` to `upsert_index.py` auto-creates/updates the `project-synonyms` map. If you prefer to manage maps in the portal, follow the manual steps below.

  * In the Azure Portal, find your AI Search service.
  * Go to **Synonym maps**.
  * Create a new map (e.g., `project-synonyms-map`).
  * Upload/copy the contents of `synonyms.seed.json` into it.
  * Go to your `drawings_unified` **Index** -\> **Fields**.
  * Select the searchable fields (`content`, `project`, `sheet_number`, `sheet_title`, `key/panel`, `key/tag`, `attributes/description`, `room_id`, `room_name`, `template_tags`, etc.).
  * In the **Synonym maps** dropdown for those fields, select your new `project-synonyms-map`.
  * Save the index.

## 4\) Quick checks (Developer Sanity Test)

> **Important:** This `query_playbook.py` script is a simple **developer sanity check** to verify a successful data load.
>
> All production query logic (including the "facts-first, sheets-fallback" pattern) is handled by your separate Azure Function. This script's only purpose is to prove that the `transform.py` and `upsert_index.py` steps worked.

Run the playbook to test the `unified_search` wrapper:

```bash
python tools/schedule_postpass/query_playbook.py
```

You should see:

  * Dishwasher in Unit A4 → a `unit_plan` FACT
  * Signed-off templates in Unit A4 → a `template` doc
  * Panel S2 schedule → `panel` FACTs (from the specific filter)
  * Main Riser Diagram → (likely) a `sheet` doc as a fallback

## 5\) Import order (recommended for full rebuild)

1.  Electrical **panel schedules** (all rows)
2.  **Unit plan schedule** (appliances: DW/Range/WH/Dryer)
3.  Mechanical **equipment** schedule
4.  **Lighting** fixture schedule
5.  Architectural: **wall/partition**, **door**, **ceiling**, **finish**
6.  **Templates** (must be last to ensure the latest foreman edit is indexed)

<!-- end list -->

```
```
