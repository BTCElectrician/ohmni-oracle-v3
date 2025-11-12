"""Sanity tests for the schedule post-pass transformer."""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

try:
    from tools.schedule_postpass import transform
except ImportError:  # pragma: no cover - fallback for direct pytest invocation
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    sys.path.append(str(repo_root))
    from tools.schedule_postpass import transform  # type: ignore

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


def _run_transform(tmp_path: pathlib.Path, templates_only: bool = False) -> subprocess.CompletedProcess:
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    templates_dir = tmp_path / "templates_root"
    in_dir.mkdir(exist_ok=True)
    out_dir.mkdir(exist_ok=True)
    templates_dir.mkdir(exist_ok=True)

    sample_sheet = {
        "project_name": "Veridian Block 1",
        "sheet_number": "E2.03",
        "sheet_title": "UNIT PLAN SCHEDULE",
        "discipline": "electrical",
        "revision": "IFC 2025-04-18",
        "revision_date": "2025-04-18",
        "source_file": "electrical/E2.03.pdf",
        "content": "Full sheet text content...",
        "blocks": [
            {
                "type": "unit schedule",
                "name": "UNIT PLAN SCHEDULE",
                "rows": [
                    {
                        "unit": "A4",
                        "device": "Dishwasher",
                        "panel": "S2",
                        "circuit": "47",
                        "voltage": "120",
                        "phase": "1",
                        "amps": "20",
                        "description": "DW GFCI"
                    },
                    {
                        "unit": "A4",
                        "device": "Range",
                        "panel": "S2",
                        "circuit": "49,51",
                        "voltage": "120/208",
                        "phase": "1",
                        "amps": "50",
                        "description": "RNG"
                    }
                ]
            },
            {
                "type": "panel schedule",
                "name": "PANEL S2",
                "rows": [
                    {"panel": "S2", "circuit": "47", "load": "Dishwasher", "amps": "20", "voltage": "120"},
                    {"panel": "S2", "circuit": "48", "load": "EM LIGHTS", "amps": "20", "voltage": "120"}
                ]
            }
        ]
    }

    sheet_file = in_dir / "E2.03_structured.json"
    if not sheet_file.exists():
        sheet_file.write_text(json.dumps(sample_sheet))

    template_file = templates_dir / "electrical" / "E2.03" / "A4.json"
    template_file.parent.mkdir(parents=True, exist_ok=True)
    if not template_file.exists():
        template_file.write_text(json.dumps(SAMPLE_TEMPLATE_ELEC))

    script_path = pathlib.Path(transform.__file__)
    cmd = [
        sys.executable,
        str(script_path),
        str(in_dir),
        str(out_dir),
        "veridian",
        "--templates-root",
        str(templates_dir),
    ]
    if templates_only:
        cmd.append("--templates-only")

    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def test_transform_full_run(tmp_path: pathlib.Path) -> None:
    _run_transform(tmp_path)
    out_dir = tmp_path / "out"

    facts_path = out_dir / "facts.jsonl"
    assert facts_path.exists()
    facts = [json.loads(line) for line in facts_path.read_text().strip().splitlines()]
    assert len(facts) == 4

    templates_path = out_dir / "templates.jsonl"
    assert templates_path.exists()
    templates = [json.loads(line) for line in templates_path.read_text().strip().splitlines()]
    assert len(templates) == 1

    unit_fact = next(f for f in facts if f["schedule_type"] == "unit_plan" and f["key"]["tag"] == "Dishwasher")
    assert unit_fact["attributes"]["panel"] == "S2"

    template_doc = templates[0]
    assert template_doc["doc_type"] == "room"
    assert template_doc["room_id"] == "A4"
    assert "signed_off" in template_doc["template_tags"]
    assert "lighting" in template_doc["template_tags"]
    assert "outlets" in template_doc["template_tags"]
    assert "gfci" in template_doc["template_tags"]
    assert "appliances" in template_doc["template_tags"]
    assert "fire_alarm" in template_doc["template_tags"]
    assert "data" in template_doc["template_tags"]
    assert template_doc["template_status"] == "signed_off"
    assert template_doc["template_payload"].startswith('{"sheet_number":')
    assert "L47" in template_doc["content"]

    coverage_path = out_dir / "coverage_report.csv"
    csv_body = coverage_path.read_text()
    assert "template_last_modified" in csv_body
    assert "E2.03,unit_plan" in csv_body
    assert "E2.03,template,1" in csv_body


def test_transform_templates_only(tmp_path: pathlib.Path) -> None:
    _run_transform(tmp_path)
    out_dir = tmp_path / "out"
    facts_before = (out_dir / "facts.jsonl").read_text()
    templates_dir = tmp_path / "templates_root"
    updated_template = dict(SAMPLE_TEMPLATE_ELEC)
    updated_template["template_status"] = "in_progress"
    (templates_dir / "electrical" / "E2.03" / "A4.json").write_text(json.dumps(updated_template))

    _run_transform(tmp_path, templates_only=True)

    templates_path = out_dir / "templates.jsonl"
    templates = [json.loads(line) for line in templates_path.read_text().strip().splitlines()]
    assert len(templates) == 1
    assert templates[0]["template_status"] == "in_progress"

    assert (out_dir / "sheets.jsonl").exists()
    assert (out_dir / "facts.jsonl").read_text() == facts_before
