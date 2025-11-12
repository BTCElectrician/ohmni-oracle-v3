"""Plumbing fixtures and water heater schedule fallback iterator."""
from __future__ import annotations

from typing import Any, Dict, Generator

from .common import ci_get


def iter_plumb_rows(raw_json: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
    """
    Yield row dicts for Plumbing schedules from nested sources.

    Supports:
      - PLUMBING.fixtures[]
      - PLUMBING.water_heaters[] or PLUMBING.waterHeaters[]
      - PLUMBING.PLUMBING_FIXTURE_SCHEDULE[]
      - PLUMBING.ELECTRIC_WATER_HEATER_SCHEDULE[]

    Normalizes fixture_id/heater_id/MARK to 'tag' for parser compatibility.
    """
    if not isinstance(raw_json, dict):
        return

    plm = None
    for k, v in raw_json.items():
        if isinstance(k, str) and k.lower() == "plumbing":
            plm = v
            break
    if not isinstance(plm, dict):
        return

    # Check multiple possible fixture schedule keys
    fixtures = (
        ci_get(plm, "fixtures", [])
        or ci_get(plm, "PLUMBING_FIXTURE_SCHEDULE", [])
        or ci_get(plm, "fixture_schedule", [])
    )
    if isinstance(fixtures, list):
        for item in fixtures:
            if isinstance(item, dict):
                row = dict(item)
                # Normalize fixture_id/MARK to tag if tag not present
                if "tag" not in row:
                    fixture_id = (
                        ci_get(row, "fixture_id")
                        or ci_get(row, "MARK")
                        or ci_get(row, "mark")
                        or ci_get(row, "id")
                    )
                    if fixture_id:
                        row["tag"] = fixture_id
                yield row

    # Check multiple possible water heater schedule keys
    heaters = (
        ci_get(plm, "water_heaters")
        or ci_get(plm, "waterHeaters")
        or ci_get(plm, "ELECTRIC_WATER_HEATER_SCHEDULE")
        or ci_get(plm, "water_heater_schedule")
    )
    if isinstance(heaters, list):
        for item in heaters:
            if isinstance(item, dict):
                row = dict(item)
                # Normalize heater_id/MARK to tag if tag not present
                if "tag" not in row:
                    heater_id = (
                        ci_get(row, "heater_id")
                        or ci_get(row, "water_heater_id")
                        or ci_get(row, "MARK")
                        or ci_get(row, "mark")
                        or ci_get(row, "id")
                    )
                    if heater_id:
                        row["tag"] = heater_id
                yield row

