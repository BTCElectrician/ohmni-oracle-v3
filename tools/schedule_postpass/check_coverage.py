#!/usr/bin/env python3
"""
Quick diagnostic script to check if structured JSON data is being properly
converted to facts for indexing.

Usage:
    python3 tools/schedule_postpass/check_coverage.py <path_to_structured_json>
"""
import json
import sys
from pathlib import Path

try:
    from tools.schedule_postpass.facts import emit_facts
    from tools.schedule_postpass.fallbacks import (
        iter_arch_rows,
        iter_mech_rows,
        iter_panel_rows,
        iter_plumb_rows,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from tools.schedule_postpass.facts import emit_facts
    from tools.schedule_postpass.fallbacks import (
        iter_arch_rows,
        iter_mech_rows,
        iter_panel_rows,
        iter_plumb_rows,
    )


def count_structured_items(raw_json: dict) -> dict:
    """Count items in structured JSON by discipline."""
    counts = {
        "electrical_panels": 0,
        "mechanical_equipment": 0,
        "plumbing_fixtures": 0,
        "architectural": 0,
    }

    # Electrical panels
    electrical = raw_json.get("ELECTRICAL", {})
    if isinstance(electrical, dict):
        panels = electrical.get("panels", [])
        if isinstance(panels, list):
            for panel in panels:
                circuits = panel.get("circuits", []) or panel.get("circuit_details", [])
                if isinstance(circuits, list):
                    counts["electrical_panels"] += len(circuits)

    # Mechanical equipment
    mechanical = raw_json.get("MECHANICAL", {})
    if isinstance(mechanical, dict):
        # Check various mechanical schedule structures
        for key, val in mechanical.items():
            if isinstance(key, str) and key.upper().endswith("_SCHEDULE"):
                if isinstance(val, dict):
                    # Check for nested lists
                    for nested_key in ("units", "fans", "devices", "equipment", "items", "rows", "louvers"):
                        nested_list = val.get(nested_key)
                        if isinstance(nested_list, list):
                            counts["mechanical_equipment"] += len(nested_list)
                elif isinstance(val, list):
                    counts["mechanical_equipment"] += len(val)
        # Also check flat equipment list
        equipment = mechanical.get("equipment")
        if isinstance(equipment, list):
            counts["mechanical_equipment"] += len(equipment)
        elif isinstance(equipment, dict):
            for _, lst in equipment.items():
                if isinstance(lst, list):
                    counts["mechanical_equipment"] += len(lst)

    # Plumbing
    plumbing = raw_json.get("PLUMBING", {})
    if isinstance(plumbing, dict):
        fixtures = plumbing.get("fixtures", []) or plumbing.get("PLUMBING_FIXTURE_SCHEDULE", [])
        if isinstance(fixtures, list):
            counts["plumbing_fixtures"] += len(fixtures)
        heaters = (
            plumbing.get("water_heaters")
            or plumbing.get("waterHeaters")
            or plumbing.get("ELECTRIC_WATER_HEATER_SCHEDULE", [])
        )
        if isinstance(heaters, list):
            counts["plumbing_fixtures"] += len(heaters)
        pumps = plumbing.get("PUMP_SCHEDULE", [])
        if isinstance(pumps, list):
            counts["plumbing_fixtures"] += len(pumps)
        shock_arrestors = plumbing.get("SHOCK_ARRESTORS", [])
        if isinstance(shock_arrestors, list):
            counts["plumbing_fixtures"] += len(shock_arrestors)
        tmv = plumbing.get("THERMOSTATIC_MIXING_VALVE_SCHEDULE", [])
        if isinstance(tmv, list):
            counts["plumbing_fixtures"] += len(tmv)

    # Architectural
    arch = raw_json.get("ARCHITECTURAL", {})
    if isinstance(arch, dict):
        for key in ("WALL_TYPES", "PARTITION_TYPES", "DOOR_SCHEDULE", "CEILING_SCHEDULE", "FINISH_SCHEDULE"):
            rows = arch.get(key, [])
            if isinstance(rows, list):
                counts["architectural"] += len(rows)

    return counts


def count_facts(raw_json: dict, sheet_number: str = "TEST") -> dict:
    """Count facts generated from structured JSON."""
    meta = {
        "tenant_id": "ohmni",
        "project": "Test Project",
        "project_id": "test",
        "sheet_number": sheet_number,
        "sheet_title": "Test Sheet",
        "discipline": "test",
        "revision": "A",
        "revision_date": "2024-01-01T00:00:00Z",
        "levels": [],
        "source_file": "test.pdf",
    }

    facts = list(emit_facts(raw_json, meta, None))
    
    counts = {
        "panel": 0,
        "mech_equipment": 0,
        "plumb_equipment": 0,
        "wall_partition": 0,
        "door": 0,
        "ceiling": 0,
        "finish": 0,
    }
    
    for fact in facts:
        stype = fact.get("schedule_type", "")
        if stype in counts:
            counts[stype] += 1
    
    return counts


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 check_coverage.py <path_to_structured_json>")
        sys.exit(1)
    
    json_path = Path(sys.argv[1])
    if not json_path.exists():
        print(f"Error: File not found: {json_path}")
        sys.exit(1)
    
    print(f"Analyzing: {json_path.name}\n")
    
    with open(json_path, "r") as f:
        raw_json = json.load(f)
    
    # Count items in structured JSON
    structured_counts = count_structured_items(raw_json)
    print("Items in structured JSON:")
    for key, count in structured_counts.items():
        if count > 0:
            print(f"  {key}: {count}")
    
    # Count facts generated
    sheet_number = raw_json.get("DRAWING_METADATA", {}).get("sheet_number", "UNKNOWN")
    fact_counts = count_facts(raw_json, sheet_number)
    print("\nFacts generated:")
    for key, count in fact_counts.items():
        if count > 0:
            print(f"  {key}: {count}")
    
    # Compare
    print("\nCoverage check:")
    electrical_structured = structured_counts["electrical_panels"]
    electrical_facts = fact_counts["panel"]
    if electrical_structured > 0:
        if electrical_facts >= electrical_structured:
            print(f"  ✓ Electrical: {electrical_facts} facts >= {electrical_structured} circuits")
        else:
            print(f"  ⚠ Electrical: {electrical_facts} facts < {electrical_structured} circuits (MISSING {electrical_structured - electrical_facts})")
    
    mech_structured = structured_counts["mechanical_equipment"]
    mech_facts = fact_counts["mech_equipment"]
    if mech_structured > 0:
        if mech_facts >= mech_structured:
            print(f"  ✓ Mechanical: {mech_facts} facts >= {mech_structured} items")
        else:
            print(f"  ⚠ Mechanical: {mech_facts} facts < {mech_structured} items (MISSING {mech_structured - mech_facts})")
    
    plumb_structured = structured_counts["plumbing_fixtures"]
    plumb_facts = fact_counts["plumb_equipment"]
    if plumb_structured > 0:
        if plumb_facts >= plumb_structured:
            print(f"  ✓ Plumbing: {plumb_facts} facts >= {plumb_structured} items")
        else:
            print(f"  ⚠ Plumbing: {plumb_facts} facts < {plumb_structured} items (MISSING {plumb_structured - plumb_facts})")
    
    arch_structured = structured_counts["architectural"]
    arch_facts = sum(fact_counts[k] for k in ("wall_partition", "door", "ceiling", "finish"))
    if arch_structured > 0:
        if arch_facts >= arch_structured:
            print(f"  ✓ Architectural: {arch_facts} facts >= {arch_structured} items")
        else:
            print(f"  ⚠ Architectural: {arch_facts} facts < {arch_structured} items (MISSING {arch_structured - arch_facts})")


if __name__ == "__main__":
    main()

