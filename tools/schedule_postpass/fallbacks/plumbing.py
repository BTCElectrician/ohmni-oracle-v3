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

    # Check for pump schedule
    pumps = ci_get(plm, "PUMP_SCHEDULE") or ci_get(plm, "pump_schedule")
    if isinstance(pumps, list):
        for item in pumps:
            if isinstance(item, dict):
                row = dict(item)
                if "tag" not in row:
                    pump_id = (
                        ci_get(row, "MARK")
                        or ci_get(row, "mark")
                        or ci_get(row, "pump_id")
                        or ci_get(row, "id")
                    )
                    if pump_id:
                        row["tag"] = pump_id
                yield row

    # Check for shock arrestors
    shock_arrestors = ci_get(plm, "SHOCK_ARRESTORS") or ci_get(plm, "shock_arrestors")
    if isinstance(shock_arrestors, list):
        for item in shock_arrestors:
            if isinstance(item, dict):
                row = dict(item)
                if "tag" not in row:
                    sa_id = (
                        ci_get(row, "MARK")
                        or ci_get(row, "mark")
                        or ci_get(row, "id")
                    )
                    if sa_id:
                        row["tag"] = sa_id
                yield row

    # Check for thermostatic mixing valve schedule
    tmv = (
        ci_get(plm, "THERMOSTATIC_MIXING_VALVE_SCHEDULE")
        or ci_get(plm, "thermostatic_mixing_valve_schedule")
    )
    if isinstance(tmv, list):
        for item in tmv:
            if isinstance(item, dict):
                row = dict(item)
                # These may not have a MARK field, so use description or model number
                if "tag" not in row:
                    tmv_id = (
                        ci_get(row, "MARK")
                        or ci_get(row, "mark")
                        or ci_get(row, "MODEL_NUMBER")
                        or ci_get(row, "model_number")
                        or ci_get(row, "VALVE_ASSEMBLY_DESIGNATION_DESCRIPTION")
                        or ci_get(row, "id")
                    )
                    if tmv_id:
                        row["tag"] = str(tmv_id)[:50]  # Truncate long descriptions
                yield row

