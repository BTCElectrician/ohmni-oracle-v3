"""Mechanical equipment schedule fallback iterator."""
from __future__ import annotations

from typing import Any, Dict, Generator

from .common import ci_get


def iter_mech_rows(raw_json: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
    """
    Yield row dicts for Mechanical equipment schedules from nested sources.

    Supports:
      - MECHANICAL.equipment (dict mapping type -> list)
      - MECHANICAL.equipment (flat list)
      - MECHANICAL.*_SCHEDULE[] (any key ending in _SCHEDULE that contains a list)
    """
    if not isinstance(raw_json, dict):
        return

    mech = None
    for k, v in raw_json.items():
        if isinstance(k, str) and k.lower() == "mechanical":
            mech = v
            break
    if not isinstance(mech, dict):
        return

    # First, try standard equipment key
    equipment = ci_get(mech, "equipment")
    if isinstance(equipment, dict):
        for _, lst in equipment.items():
            if isinstance(lst, list):
                for item in lst:
                    if isinstance(item, dict):
                        yield item
    elif isinstance(equipment, list):
        for item in equipment:
            if isinstance(item, dict):
                yield item

    # Also check for any keys ending in _SCHEDULE (case-insensitive)
    # These may be dicts with nested lists (e.g., EXHAUST_FAN_SCHEDULE.fans[])
    for key, val in mech.items():
        if isinstance(key, str) and key.upper().endswith("_SCHEDULE"):
            if isinstance(val, list):
                # Direct list of items
                for item in val:
                    if isinstance(item, dict):
                        yield item
            elif isinstance(val, dict):
                # Dict with nested lists - check common keys like 'fans', 'devices', 'units', 'equipment', 'louvers'
                for nested_key in ("fans", "devices", "units", "equipment", "items", "rows", "louvers"):
                    nested_list = ci_get(val, nested_key)
                    if isinstance(nested_list, list):
                        for item in nested_list:
                            if isinstance(item, dict):
                                row = dict(item)
                                # Normalize DESIG./DESIG to tag if tag not present
                                if "tag" not in row:
                                    tag = (
                                        ci_get(row, "DESIG.")
                                        or ci_get(row, "DESIG")
                                        or ci_get(row, "tag")
                                        or ci_get(row, "TAG")
                                        or ci_get(row, "name")
                                        or ci_get(row, "NAME")
                                        or ci_get(row, "mark")
                                        or ci_get(row, "MARK")
                                    )
                                    if tag:
                                        row["tag"] = tag
                                yield row

