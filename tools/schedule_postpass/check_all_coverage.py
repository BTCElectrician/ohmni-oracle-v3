#!/usr/bin/env python3
"""
Batch coverage checker for all structured JSON files in a processed directory.

This script recursively finds all *_structured.json files and checks coverage
for each one, reporting any missing items.

Usage:
    python3 tools/schedule_postpass/check_all_coverage.py <path_to_processed_directory>
    
Example:
    python3 tools/schedule_postpass/check_all_coverage.py /path/to/job/processed
"""
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

try:
    from tools.schedule_postpass.facts import emit_facts
    from tools.schedule_postpass.check_coverage import count_structured_items, count_facts
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from tools.schedule_postpass.facts import emit_facts
    from tools.schedule_postpass.check_coverage import count_structured_items, count_facts


def find_structured_json_files(root_path: Path) -> List[Path]:
    """Recursively find all *_structured.json files."""
    return list(root_path.rglob("*_structured.json"))


def check_file_coverage(json_path: Path) -> Tuple[bool, Dict, Dict, str]:
    """
    Check coverage for a single structured JSON file.
    
    Returns:
        (is_ok, structured_counts, fact_counts, sheet_number)
    """
    try:
        with open(json_path, "r") as f:
            raw_json = json.load(f)
    except Exception as e:
        return False, {}, {}, f"Error reading file: {e}"

    sheet_number = raw_json.get("DRAWING_METADATA", {}).get("sheet_number", "UNKNOWN")
    structured_counts = count_structured_items(raw_json)
    fact_counts = count_facts(raw_json, sheet_number)

    # Check for issues
    issues = []
    is_ok = True

    # Electrical
    elec_structured = structured_counts.get("electrical_panels", 0)
    elec_facts = fact_counts.get("panel", 0)
    if elec_structured > 0:
        if elec_facts < elec_structured:
            is_ok = False
            issues.append(f"Electrical: {elec_facts} facts < {elec_structured} circuits (MISSING {elec_structured - elec_facts})")

    # Mechanical
    mech_structured = structured_counts.get("mechanical_equipment", 0)
    mech_facts = fact_counts.get("mech_equipment", 0)
    if mech_structured > 0:
        if mech_facts < mech_structured:
            is_ok = False
            issues.append(f"Mechanical: {mech_facts} facts < {mech_structured} items (MISSING {mech_structured - mech_facts})")

    # Plumbing
    plumb_structured = structured_counts.get("plumbing_fixtures", 0)
    plumb_facts = fact_counts.get("plumb_equipment", 0)
    if plumb_structured > 0:
        if plumb_facts < plumb_structured:
            is_ok = False
            issues.append(f"Plumbing: {plumb_facts} facts < {plumb_structured} items (MISSING {plumb_structured - plumb_facts})")

    # Architectural
    arch_structured = structured_counts.get("architectural", 0)
    arch_facts = sum(fact_counts.get(k, 0) for k in ("wall_partition", "door", "ceiling", "finish"))
    if arch_structured > 0:
        if arch_facts < arch_structured:
            is_ok = False
            issues.append(f"Architectural: {arch_facts} facts < {arch_structured} items (MISSING {arch_structured - arch_facts})")

    return is_ok, structured_counts, fact_counts, "\n".join(issues) if issues else "OK"


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 check_all_coverage.py <path_to_processed_directory>")
        sys.exit(1)

    root_path = Path(sys.argv[1])
    if not root_path.exists():
        print(f"Error: Directory not found: {root_path}")
        sys.exit(1)

    print(f"Scanning for structured JSON files in: {root_path}\n")
    json_files = find_structured_json_files(root_path)
    
    if not json_files:
        print("No *_structured.json files found.")
        sys.exit(0)

    print(f"Found {len(json_files)} structured JSON files\n")
    print("=" * 80)

    issues_found = []
    total_checked = 0
    total_ok = 0

    for json_path in sorted(json_files):
        total_checked += 1
        relative_path = json_path.relative_to(root_path)
        is_ok, structured_counts, fact_counts, status = check_file_coverage(json_path)

        if is_ok:
            total_ok += 1
            print(f"✓ {relative_path}")
            # Show summary if there's data
            if any(structured_counts.values()):
                summary = ", ".join(
                    f"{k}={v}" for k, v in structured_counts.items() if v > 0
                )
                print(f"  {summary} → All captured")
        else:
            issues_found.append((relative_path, status))
            print(f"⚠ {relative_path}")
            print(f"  {status}")

    print("=" * 80)
    print(f"\nSummary: {total_ok}/{total_checked} files passed coverage check")

    if issues_found:
        print(f"\n⚠ ISSUES FOUND in {len(issues_found)} files:")
        for path, issue in issues_found:
            print(f"  {path}: {issue}")
        print("\nNext steps:")
        print("  1. Review the structured JSON files with issues")
        print("  2. Check if new schedule types or structures need fallback support")
        print("  3. See tools/schedule_postpass/README.md section 7 for extending fallbacks")
        sys.exit(1)
    else:
        print("\n✓ All files passed coverage check!")
        sys.exit(0)


if __name__ == "__main__":
    main()

