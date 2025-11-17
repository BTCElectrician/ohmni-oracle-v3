"""
Electrical normalization utilities.
Handles panel schedules, circuits, and electrical system data.
"""
import re
import logging
from typing import Dict, Any, Optional, List

from .common import safe_int

logger = logging.getLogger(__name__)


def extract_panel_circuit_number(data: Dict[str, Any]) -> Optional[int]:
    """Locate a circuit number from common key variations."""
    if not isinstance(data, dict):
        return None
    circuit_keys = [
        "circuit_number",
        "circuit",
        "ckt",
        "circuit_no",
        "no",
        "#",
        "number",
        "branch",
        "cct",
        "cct_no",
    ]
    for key in circuit_keys:
        if key in data:
            num = safe_int(data.get(key))
            if num is not None:
                return num
    return None


def normalize_phase_loads(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return consistent phase load dict (A/B/C)."""
    if not isinstance(data, dict):
        return {"A": None, "B": None, "C": None}

    phase_loads = data.get("phase_loads")
    if isinstance(phase_loads, dict):
        return {
            "A": phase_loads.get("A"),
            "B": phase_loads.get("B"),
            "C": phase_loads.get("C"),
        }

    return {
        "A": data.get("A") or data.get("va_phase_a"),
        "B": data.get("B") or data.get("va_phase_b"),
        "C": data.get("C") or data.get("va_phase_c"),
    }


def _has_panel_value(value: Any) -> bool:
    """Determine whether a field contains meaningful data."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _panel_side_is_empty(side: Optional[Dict[str, Any]]) -> bool:
    """Return True if a right_side/paired circuit contains no usable data."""
    if not isinstance(side, dict):
        return True

    if _has_panel_value(side.get("circuit_number")):
        return False

    for key in ("load_name", "load_classification", "trip", "poles"):
        if _has_panel_value(side.get(key)):
            return False

    phase_loads = side.get("phase_loads") or {}
    if any(_has_panel_value(phase_loads.get(phase)) for phase in ("A", "B", "C")):
        return False

    return True


def _panel_entry_to_side(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a normalized circuit entry into a right_side structure."""
    return {
        "circuit_number": extract_panel_circuit_number(entry),
        "load_classification": entry.get("load_classification"),
        "load_name": entry.get("load_name"),
        "trip": entry.get("trip"),
        "poles": entry.get("poles"),
        "phase_loads": normalize_phase_loads(entry),
    }


def normalize_panel_side_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a single side (left/right) of a panel schedule row."""
    if not isinstance(data, dict):
        return {
            "circuit_number": None,
            "load_classification": None,
            "load_name": None,
            "trip": None,
            "poles": None,
            "phase_loads": {"A": None, "B": None, "C": None},
        }

    circuit_number = extract_panel_circuit_number(data)
    load_name = data.get("load_name") or data.get("description") or data.get("load")
    trip = data.get("trip") or data.get("breaker") or data.get("amps")
    poles = data.get("poles") or data.get("pole") or data.get("phases")

    normalized = {
        "circuit_number": circuit_number,
        "load_classification": data.get("load_classification")
        or data.get("classification"),
        "load_name": load_name,
        "trip": str(trip).strip() if isinstance(trip, str) else trip,
        "poles": safe_int(poles) if poles is not None else None,
        "phase_loads": normalize_phase_loads(data),
    }
    return normalized


def normalize_panels_list_entry(entry: Any, panel_name: str, index: int) -> Dict[str, Any]:
    """Normalize entries under ELECTRICAL.panels[].circuits."""
    if not isinstance(entry, dict):
        logger.warning(
            f"Unexpected panel circuit entry type in panel '{panel_name}' index {index}: {entry}"
        )
        return {
            "circuit_number": None,
            "load_classification": None,
            "load_name": None,
            "trip": None,
            "poles": None,
            "phase_loads": {"A": None, "B": None, "C": None},
            "right_side": normalize_panel_side_data({}),
        }

    # Case 1: Newer structure with explicit left/right objects
    if "left" in entry or "right" in entry:
        left_side = normalize_panel_side_data(entry.get("left") or {})
        right_side = normalize_panel_side_data(entry.get("right") or {})

        # If left side missing but right present, swap to keep numbering intact
        if (
            left_side.get("circuit_number") is None
            and right_side.get("circuit_number") is not None
        ):
            left_side, right_side = right_side, normalize_panel_side_data({})

        normalized = {
            "circuit_number": left_side.get("circuit_number"),
            "load_classification": left_side.get("load_classification"),
            "load_name": left_side.get("load_name"),
            "trip": left_side.get("trip"),
            "poles": left_side.get("poles"),
            "phase_loads": left_side.get("phase_loads"),
            "right_side": right_side,
        }
        return normalized

    # Case 2: Already in expected structure
    normalized = entry.copy()

    if "phase_loads" not in normalized or not isinstance(
        normalized.get("phase_loads"), dict
    ):
        normalized["phase_loads"] = normalize_phase_loads(normalized)

    if "right_side" in normalized:
        normalized["right_side"] = normalize_panel_side_data(
            normalized.get("right_side") or {}
        )
        if _panel_side_is_empty(normalized["right_side"]):
            normalized.pop("right_side", None)

    if normalized.get("circuit_number") is None:
        normalized["circuit_number"] = extract_panel_circuit_number(normalized)

    return normalized


def normalize_single_circuit(
    circuit_data: Dict[str, Any], panel_name: str, index: int
) -> Dict[str, Any]:
    """
    Normalizes keys for one circuit dictionary.
    Flexible synonyms for 'circuit', 'trip', 'poles', 'load_name', etc.
    """
    if not isinstance(circuit_data, dict):
        logger.warning(
            f"Non-dict circuit at index {index} in panel '{panel_name}': {circuit_data}"
        )
        return circuit_data

    normalized = circuit_data.copy()

    # Potential synonyms
    synonyms_map = {
        "circuit": [
            "circuit_no",
            "ckt",
            "circuit_number",
            "#",
            "no",
            "ckt_no",
            "circuit_num",
            "cct",
            "cct_no",
            "circuit_id",
            "number",
            "branch",
            "branch_no",
        ],
        "load_name": [
            "description",
            "equipment",
            "load description",
            "serves",
            "item",
            "connected_to",
            "load",
            "device",
            "designation",
            "usage",
            "purpose",
            "notes",
            "function",
            "servicing",
            "area_served",
            "room",
            "location",
            "powered_device",
        ],
        "trip": [
            "breaker",
            "amps",
            "size",
            "rating",
            "amp",
            "ocp",
            "breaker_size",
            "amperage",
            "ampacity",
            "amp_rating",
            "trip_size",
            "breaker_rating",
            "ocpd",
            "overcurrent",
            "amp_trip",
            "current",
            "current_rating",
            "a",
            "protection",
        ],
        "poles": [
            "pole",
            "p",
            "#p",
            "no_poles",
            "num_poles",
            "pole_count",
            "phases",
            "phase",
            "num_phases",
            "number_of_poles",
            "number_poles",
            "ph",
            "p#",
            "num_p",
        ],
        "va_phase_a": [
            "va a",
            "phase a",
            "ph a",
            "a va",
            "va_a",
            "phase_a",
            "a_phase",
            "a_load",
            "va_phase_1",
            "phase_1",
            "ph_a",
            "va_a_phase",
            "load_a",
            "ph1",
            "phase1",
            "ph_1",
            "phase_1_load",
        ],
        "va_phase_b": [
            "va b",
            "phase b",
            "ph b",
            "b va",
            "va_b",
            "phase_b",
            "b_phase",
            "b_load",
            "va_phase_2",
            "phase_2",
            "ph_b",
            "va_b_phase",
            "load_b",
            "ph2",
            "phase2",
            "ph_2",
            "phase_2_load",
        ],
        "va_phase_c": [
            "va c",
            "phase c",
            "ph c",
            "c va",
            "va_c",
            "phase_c",
            "c_phase",
            "c_load",
            "va_phase_3",
            "phase_3",
            "ph_c",
            "va_c_phase",
            "load_c",
            "ph3",
            "phase3",
            "ph_3",
            "phase_3_load",
        ],
        "total_va": [
            "va total",
            "connected va",
            "kva",
            "total_kva",
            "connected_load",
            "load",
            "total",
            "sum",
            "total_load",
            "connected",
            "va_total",
            "total_connected",
            "kva_total",
            "va_sum",
            "load_total",
            "demand",
            "total_demand",
            "volt_amps",
        ],
    }

    for target_key, possible_synonyms in synonyms_map.items():
        found_key = None
        if target_key in normalized:
            found_key = target_key
        else:
            # Look for synonyms
            for syn in possible_synonyms:
                if syn in normalized:
                    found_key = syn
                    break
        if found_key:
            # Attempt conversions for numeric fields
            value = normalized[found_key]
            try:
                if target_key == "poles":
                    # Poles -> int
                    if isinstance(value, (int, float)):
                        pass
                    elif isinstance(value, str):
                        # e.g., "3 P"
                        parts = value.strip().split()
                        value = int(parts[0]) if parts else 0
                    else:
                        value = 0
                elif target_key in [
                    "va_phase_a",
                    "va_phase_b",
                    "va_phase_c",
                    "total_va",
                ]:
                    if isinstance(value, (int, float)):
                        pass
                    elif isinstance(value, str):
                        numeric = re.sub(r"[^\d.]", "", value)
                        if "." in numeric:
                            value = float(numeric)
                        elif numeric:
                            value = int(numeric)
                        else:
                            value = 0
                    else:
                        value = 0
                elif target_key in ["circuit", "trip", "load_name"]:
                    # keep as string
                    value = str(value).strip()
            except Exception as e:
                logger.warning(
                    f"Normalization error in panel '{panel_name}', circuit index {index}, key '{found_key}': {e}"
                )

            # Move the value to the canonical target_key if different
            if found_key != target_key:
                del normalized[found_key]
            normalized[target_key] = value

    return normalized


def validate_panel_structure(electrical: Dict[str, Any]) -> None:
    """Validate and correct panel schedule structure if needed."""
    panel_schedules = electrical.get("PANEL_SCHEDULES")

    # If we have a dict (object), ensure each panel has required properties
    if isinstance(panel_schedules, dict):
        for panel_name, panel_data in panel_schedules.items():
            if isinstance(panel_data, dict):
                # Ensure circuit_details is present
                if "circuit_details" not in panel_data:
                    panel_data["circuit_details"] = []

                # Check if circuits have circuit numbers
                circuits = panel_data.get("circuit_details", [])
                if circuits and all("circuit" not in ckt for ckt in circuits):
                    # Try to infer circuit numbers
                    for i, ckt in enumerate(circuits):
                        # Add circuit number if missing
                        ckt["circuit"] = str(i + 1)


def _pair_panel_circuits(circuits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Pair sequential odd/even circuits so the even entry becomes right_side data.
    Returns a new list without duplicating even-numbered circuits.
    """
    if not isinstance(circuits, list):
        return circuits

    paired: List[Dict[str, Any]] = []
    pending_left: Optional[Dict[str, Any]] = None

    def flush_pending() -> None:
        nonlocal pending_left
        if pending_left:
            right_side = pending_left.get("right_side")
            if right_side and _panel_side_is_empty(right_side):
                pending_left.pop("right_side", None)
            paired.append(pending_left)
            pending_left = None

    for entry in circuits:
        if not isinstance(entry, dict):
            flush_pending()
            paired.append(entry)
            continue

        # Normalize an existing right_side if present
        if "right_side" in entry:
            normalized_side = normalize_panel_side_data(entry.get("right_side") or {})
            if _panel_side_is_empty(normalized_side):
                entry.pop("right_side", None)
            else:
                entry["right_side"] = normalized_side

        number = safe_int(entry.get("circuit_number"))
        has_right_side = (
            "right_side" in entry and not _panel_side_is_empty(entry.get("right_side"))
        )

        # Already paired entry - keep as-is
        if has_right_side:
            flush_pending()
            paired.append(entry)
            continue

        if number is None:
            flush_pending()
            paired.append(entry)
            continue

        if number % 2 == 1:
            flush_pending()
            pending_left = entry
            continue

        # Even circuit: try to attach to pending odd
        if pending_left and safe_int(pending_left.get("circuit_number")) is not None:
            expected_even = safe_int(pending_left.get("circuit_number")) + 1
        else:
            expected_even = None

        if pending_left and expected_even == number:
            pending_left["right_side"] = _panel_entry_to_side(entry)
            continue

        # No matching odd - emit this even as its own row
        flush_pending()
        paired.append(entry)

    flush_pending()
    return paired


def normalize_panel_fields(parsed_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    If present, navigate to ELECTRICAL -> PANEL_SCHEDULES (object or array).
    For each schedule, normalize the panel's circuits.
    """
    if not isinstance(parsed_json, dict):
        logger.warning("Expected dict at top-level for panel normalization.")
        return parsed_json

    electrical = parsed_json.get("ELECTRICAL")
    if not isinstance(electrical, dict):
        return parsed_json

    # Handle both object and array structures for backward compatibility
    panel_schedules = electrical.get("PANEL_SCHEDULES")

    # If panel_schedules is a dict (object), process each panel by name
    if isinstance(panel_schedules, dict):
        for panel_name, panel_data in panel_schedules.items():
            if isinstance(panel_data, dict):
                # Ensure circuit_details exists and is a list
                circuit_details = panel_data.get("circuit_details", [])
                if isinstance(circuit_details, list):
                    normalized_circuits = []
                    for i, ckt in enumerate(circuit_details):
                        normalized_circuits.append(
                            normalize_single_circuit(ckt, panel_name, i)
                        )
                    panel_data["circuit_details"] = _pair_panel_circuits(
                        normalized_circuits
                    )
                else:
                    logger.warning(
                        f"Panel '{panel_name}' has a non-list 'circuit_details' field."
                    )

    # Handle legacy array format
    elif isinstance(panel_schedules, list):
        normalized_schedules = []
        for schedule_obj in panel_schedules:
            if not isinstance(schedule_obj, dict):
                normalized_schedules.append(schedule_obj)
                continue
            # Process as before for array format
            panel_data = schedule_obj.get("panel")
            if not isinstance(panel_data, dict):
                normalized_schedules.append(schedule_obj)
                continue

            panel_name = panel_data.get("name", "UnknownPanel")
            circuits = panel_data.get("circuits", [])
            if isinstance(circuits, list):
                normalized_circuits = []
                for i, ckt in enumerate(circuits):
                    normalized_circuits.append(
                        normalize_single_circuit(ckt, panel_name, i)
                    )
                panel_data["circuits"] = _pair_panel_circuits(normalized_circuits)
            else:
                logger.warning(
                    f"Panel '{panel_name}' has a non-list 'circuits' field."
                )
            normalized_schedules.append(schedule_obj)

        electrical["PANEL_SCHEDULES"] = normalized_schedules

    # Additional validation and correction
    validate_panel_structure(electrical)

    # Also handle ELECTRICAL.panels (alternate structure used elsewhere)
    try:
        panels = electrical.get("panels")
        if isinstance(panels, list):
            for panel in panels:
                if not isinstance(panel, dict):
                    continue
                circuits = panel.get("circuits")
                if isinstance(circuits, list):
                    panel_name = panel.get("panel_name", "UnknownPanel")
                    normalized_circuits = []
                    for i, entry in enumerate(circuits):
                        normalized_circuits.append(
                            normalize_panels_list_entry(entry, panel_name, i)
                        )

                    def _sort_key(row: Dict[str, Any]) -> int:
                        num = row.get("circuit_number")
                        parsed = safe_int(num)
                        return parsed if parsed is not None else 10**9

                    sorted_circuits = sorted(normalized_circuits, key=_sort_key)
                    panel["circuits"] = _pair_panel_circuits(sorted_circuits)
    except Exception as e:
        logger.debug(f"Panel list post-processing note: {e}")

    return parsed_json

