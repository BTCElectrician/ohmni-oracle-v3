"""Electrical panel schedule fallback iterator."""
from __future__ import annotations

from typing import Any, Dict, Generator, Optional

from .common import (
    ci_get,
    extract_text_from_phase_loads,
    first_non_empty,
)


def iter_panel_rows(raw_json: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
    """
    Yield synthesized 'row' dicts for Electrical panel schedules from nested sources.

    Supports shapes:
      - ELECTRICAL.panels[].circuits[]
      - ELECTRICAL.PANEL_SCHEDULES{panel_name}.circuit_details[] / .circuits[]
      - ELECTRICAL.panel_schedules[] with inner .circuits[] / .circuit_details[]
    
    Also handles paired circuits (left/right side) and extracts descriptive text from phase_loads.
    """
    if not isinstance(raw_json, dict):
        return

    electrical = None
    for k, v in raw_json.items():
        if isinstance(k, str) and k.lower() == "electrical":
            electrical = v
            break
    if not isinstance(electrical, dict):
        return

    def _yield_rows(panel_name: Optional[str], circuits: Any, panel_voltage: Any = None) -> Generator[Dict[str, Any], None, None]:
        if not isinstance(circuits, list):
            return
        for entry in circuits:
            if not isinstance(entry, dict):
                continue
            
            # Extract primary circuit data
            circuit_num = first_non_empty(
                ci_get(entry, "circuit"),
                ci_get(entry, "circuit_number"),
                ci_get(entry, "ckt"),
                ci_get(entry, "cct"),
                ci_get(ci_get(entry, "left") or {}, "circuit_number"),
            )
            description = first_non_empty(
                ci_get(entry, "load_name"),
                ci_get(entry, "description"),
                ci_get(entry, "load"),
                ci_get(entry, "device"),
            )
            # If description is empty, try extracting from phase_loads
            if not description:
                phase_loads = ci_get(entry, "phase_loads")
                description = extract_text_from_phase_loads(phase_loads)
            
            amps = first_non_empty(
                ci_get(entry, "trip"),
                ci_get(entry, "amps"),
                ci_get(entry, "breaker"),
                ci_get(entry, "size"),
            )
            phase_or_poles = first_non_empty(
                ci_get(entry, "phase"),
                ci_get(entry, "poles"),
                ci_get(entry, "pole"),
                ci_get(entry, "phase_count"),
            )
            
            # Yield primary circuit if it has a circuit number
            if circuit_num:
                row: Dict[str, Any] = {
                    "panel": panel_name,
                    "circuit": circuit_num,
                    "description": description,
                    "amps": amps,
                }
                if panel_voltage:
                    row["voltage"] = panel_voltage
                if phase_or_poles is not None:
                    row["phase"] = phase_or_poles
                    row["poles"] = phase_or_poles
                yield row
            
            # Extract and yield right_side/paired circuit data
            right_side = ci_get(entry, "right_side")
            right_circuit_num = None
            right_description = None
            right_amps = None
            right_poles = None
            
            # Try right_side object first
            if isinstance(right_side, dict):
                right_circuit_num = first_non_empty(
                    ci_get(right_side, "circuit_number"),
                    ci_get(right_side, "circuit"),
                    ci_get(right_side, "ckt"),
                    ci_get(right_side, "cct"),
                )
                right_description = first_non_empty(
                    ci_get(right_side, "load_name"),
                    ci_get(right_side, "description"),
                    ci_get(right_side, "load"),
                )
                # Extract from right_side phase_loads if description is empty
                if not right_description:
                    right_phase_loads = ci_get(right_side, "phase_loads")
                    right_description = extract_text_from_phase_loads(right_phase_loads)
                right_amps = first_non_empty(
                    ci_get(right_side, "trip"),
                    ci_get(right_side, "amps"),
                    ci_get(right_side, "breaker"),
                )
                right_poles = first_non_empty(
                    ci_get(right_side, "poles"),
                    ci_get(right_side, "pole"),
                    ci_get(right_side, "phase"),
                )
            
            # Fallback to _b suffixed fields if right_side didn't provide circuit number
            if not right_circuit_num:
                right_circuit_num = first_non_empty(
                    ci_get(entry, "ckt_b"),
                    ci_get(entry, "circuit_b"),
                    ci_get(entry, "circuit_number_b"),
                )
                if not right_description:
                    right_description = first_non_empty(
                        ci_get(entry, "load_name_b"),
                        ci_get(entry, "description_b"),
                        ci_get(entry, "load_b"),
                    )
                if not right_amps:
                    right_amps = first_non_empty(
                        ci_get(entry, "trip_b"),
                        ci_get(entry, "amps_b"),
                        ci_get(entry, "breaker_b"),
                    )
                if not right_poles:
                    right_poles = first_non_empty(
                        ci_get(entry, "poles_b"),
                        ci_get(entry, "pole_b"),
                        ci_get(entry, "phase_b"),
                    )
            
            # Also check main entry's phase_loads for descriptive text if still no description
            # (descriptive text in phase_loads may describe the right side circuit)
            if not right_description:
                main_phase_loads = ci_get(entry, "phase_loads")
                right_description = extract_text_from_phase_loads(main_phase_loads)
            
            # Yield right side circuit if it has a circuit number
            if right_circuit_num:
                right_row: Dict[str, Any] = {
                    "panel": panel_name,
                    "circuit": right_circuit_num,
                    "description": right_description,
                    "amps": right_amps,
                }
                if panel_voltage:
                    right_row["voltage"] = panel_voltage
                if right_poles is not None:
                    right_row["phase"] = right_poles
                    right_row["poles"] = right_poles
                yield right_row

    panels = ci_get(electrical, "panels", [])
    if isinstance(panels, list):
        for p in panels:
            if not isinstance(p, dict):
                continue
            pname = first_non_empty(
                ci_get(p, "panel_name"),
                ci_get(p, "panel_id"),
                ci_get(p, "name"),
                ci_get(p, "panel"),
                ci_get(p, "id"),
            )
            pvoltage = ci_get(p, "voltage")
            if not pvoltage:
                enclosure = ci_get(p, "enclosure_info")
                if isinstance(enclosure, dict):
                    pvoltage = ci_get(enclosure, "volts") or ci_get(enclosure, "voltage")
            circuits = ci_get(p, "circuits", []) or ci_get(p, "circuit_details", [])
            yield from _yield_rows(pname, circuits, pvoltage)

    panel_schedules = None
    for key in ("PANEL_SCHEDULES", "panel_schedules", "panel schedules", "panelschedules"):
        panel_schedules = ci_get(electrical, key)
        if panel_schedules is not None:
            break
    if isinstance(panel_schedules, dict):
        for pname, pdata in panel_schedules.items():
            if not isinstance(pdata, dict):
                continue
            circuits = ci_get(pdata, "circuit_details", []) or ci_get(pdata, "circuits", [])
            pvoltage = ci_get(pdata, "voltage")
            yield from _yield_rows(pname, circuits, pvoltage)
    elif isinstance(panel_schedules, list):
        for p in panel_schedules:
            if not isinstance(p, dict):
                continue
            pname = first_non_empty(
                ci_get(p, "panel_name"),
                ci_get(p, "panel_id"),
                ci_get(p, "name"),
                ci_get(p, "panel"),
                ci_get(p, "id"),
            )
            pvoltage = ci_get(p, "voltage")
            if not pvoltage:
                enclosure = ci_get(p, "enclosure_info")
                if isinstance(enclosure, dict):
                    pvoltage = ci_get(enclosure, "volts") or ci_get(enclosure, "voltage")
            circuits = ci_get(p, "circuit_details", []) or ci_get(p, "circuits", [])
            yield from _yield_rows(pname, circuits, pvoltage)

