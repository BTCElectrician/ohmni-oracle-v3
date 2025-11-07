"""
Normalization utilities for structured data.
Extracted from file_processor.py to reduce complexity.
"""
import re
import logging
from typing import Dict, Any, Optional
from utils.performance_utils import time_operation_context

logger = logging.getLogger(__name__)


def _safe_int(value: Any) -> Optional[int]:
    """Convert various value types to int if possible."""
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        try:
            return int(value)
        except Exception:
            return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        match = re.search(r"-?\d+", stripped)
        if match:
            try:
                return int(match.group(0))
            except Exception:
                return None
    return None


def _extract_panel_circuit_number(data: Dict[str, Any]) -> Optional[int]:
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
            num = _safe_int(data.get(key))
            if num is not None:
                return num
    return None


def _normalize_phase_loads(data: Dict[str, Any]) -> Dict[str, Any]:
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


def _normalize_panel_side_data(data: Dict[str, Any]) -> Dict[str, Any]:
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

    circuit_number = _extract_panel_circuit_number(data)
    load_name = data.get("load_name") or data.get("description") or data.get("load")
    trip = data.get("trip") or data.get("breaker") or data.get("amps")
    poles = data.get("poles") or data.get("pole") or data.get("phases")

    normalized = {
        "circuit_number": circuit_number,
        "load_classification": data.get("load_classification")
        or data.get("classification"),
        "load_name": load_name,
        "trip": str(trip).strip() if isinstance(trip, str) else trip,
        "poles": _safe_int(poles) if poles is not None else None,
        "phase_loads": _normalize_phase_loads(data),
    }
    return normalized


def _normalize_panels_list_entry(entry: Any, panel_name: str, index: int) -> Dict[str, Any]:
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
            "right_side": _normalize_panel_side_data({}),
        }

    # Case 1: Newer structure with explicit left/right objects
    if "left" in entry or "right" in entry:
        left_side = _normalize_panel_side_data(entry.get("left") or {})
        right_side = _normalize_panel_side_data(entry.get("right") or {})

        # If left side missing but right present, swap to keep numbering intact
        if (
            left_side.get("circuit_number") is None
            and right_side.get("circuit_number") is not None
        ):
            left_side, right_side = right_side, _normalize_panel_side_data({})

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
        normalized["phase_loads"] = _normalize_phase_loads(normalized)

    if "right_side" in normalized:
        normalized["right_side"] = _normalize_panel_side_data(
            normalized.get("right_side") or {}
        )
    else:
        normalized["right_side"] = _normalize_panel_side_data({})

    if normalized.get("circuit_number") is None:
        normalized["circuit_number"] = _extract_panel_circuit_number(normalized)

    return normalized


def _normalize_single_circuit(
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
                            _normalize_single_circuit(ckt, panel_name, i)
                        )
                    panel_data["circuit_details"] = normalized_circuits
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
                        _normalize_single_circuit(ckt, panel_name, i)
                    )
                panel_data["circuits"] = normalized_circuits
            else:
                logger.warning(
                    f"Panel '{panel_name}' has a non-list 'circuits' field."
                )
            normalized_schedules.append(schedule_obj)

        electrical["PANEL_SCHEDULES"] = normalized_schedules

    # Additional validation and correction
    _validate_panel_structure(electrical)

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
                            _normalize_panels_list_entry(entry, panel_name, i)
                        )

                    def _sort_key(row: Dict[str, Any]) -> int:
                        num = row.get("circuit_number")
                        parsed = _safe_int(num)
                        return parsed if parsed is not None else 10**9

                    panel["circuits"] = sorted(normalized_circuits, key=_sort_key)
    except Exception as e:
        logger.debug(f"Panel list post-processing note: {e}")

    return parsed_json


def _validate_panel_structure(electrical: Dict[str, Any]) -> None:
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


def normalize_mechanical_schedule(parsed_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize mechanical schedule fields with consistent naming.
    Handles equipment schedules, air devices, diffusers, etc.
    """
    if not isinstance(parsed_json, dict):
        logger.warning("Expected dict at top-level for mechanical normalization.")
        return parsed_json

    mechanical = parsed_json.get("MECHANICAL")
    if not isinstance(mechanical, dict):
        # No mechanical data found
        return parsed_json

    # Handle equipment schedules
    equipment = mechanical.get("equipment")
    if isinstance(equipment, dict):
        # equipment already properly structured
        pass
    elif isinstance(equipment, list):
        # Convert flat list to categorized dictionary
        equipment_by_type = {}
        for item in equipment:
            if isinstance(item, dict):
                # Try to determine equipment type
                equip_type = _get_equipment_type(item)
                if equip_type not in equipment_by_type:
                    equipment_by_type[equip_type] = []
                equipment_by_type[equip_type].append(item)
        mechanical["equipment"] = equipment_by_type

    # Handle other mechanical schedules if needed
    # [Add more normalization logic for other mechanical subtypes as needed]

    return parsed_json


def _get_equipment_type(equipment_item: Dict[str, Any]) -> str:
    """Helper function to determine equipment type from item data."""
    # Check for explicit type field
    type_field = equipment_item.get("type") or equipment_item.get("equipment_type")
    if type_field and isinstance(type_field, str):
        if "fan" in type_field.lower():
            return "fans"
        elif "pump" in type_field.lower():
            return "pumps"
        elif "unit" in type_field.lower() or "ahu" in type_field.lower():
            return "airHandlingUnits"
        elif "vav" in type_field.lower():
            return "vavBoxes"
        elif "chiller" in type_field.lower():
            return "chillers"
        elif "boiler" in type_field.lower():
            return "boilers"

    # Check ID/mark field patterns
    id_field = equipment_item.get("id") or equipment_item.get("mark") or ""
    if isinstance(id_field, str):
        id_prefix = id_field.upper()[:3] if id_field else ""
        if id_prefix.startswith("AHU"):
            return "airHandlingUnits"
        elif id_prefix.startswith("EF") or id_prefix.startswith("SF"):
            return "fans"
        elif id_prefix.startswith("VAV"):
            return "vavBoxes"
        elif id_prefix.startswith("FCU"):
            return "fanCoilUnits"
        elif id_prefix.startswith("CH"):
            return "chillers"
        elif id_prefix.startswith("B-"):
            return "boilers"
        elif id_prefix.startswith("P-"):
            return "pumps"

    # Default category
    return "generalEquipment"


def normalize_plumbing_schedule(parsed_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize plumbing schedule fields with consistent naming.
    Handles fixture schedules, water heater schedules, and piping schedules.
    """
    if not isinstance(parsed_json, dict):
        logger.warning("Expected dict at top-level for plumbing normalization.")
        return parsed_json

    plumbing = parsed_json.get("PLUMBING")
    if not isinstance(plumbing, dict):
        # No plumbing data found, or it's not structured as expected
        return parsed_json

    # Normalize fixtures data
    fixtures = plumbing.get("fixtures")
    if isinstance(fixtures, list):
        normalized_fixtures = []
        for fixture in fixtures:
            if isinstance(fixture, dict):
                normalized_fixture = _normalize_plumbing_fixture(fixture)
                normalized_fixtures.append(normalized_fixture)
            else:
                normalized_fixtures.append(fixture)
        plumbing["fixtures"] = normalized_fixtures

    # Normalize water heaters data
    water_heaters = plumbing.get("water_heaters") or plumbing.get("waterHeaters")
    if water_heaters is not None:
        # Ensure consistent key naming
        if "waterHeaters" in plumbing:
            plumbing["water_heaters"] = plumbing.pop("waterHeaters")

        if isinstance(plumbing["water_heaters"], list):
            normalized_heaters = []
            for heater in plumbing["water_heaters"]:
                if isinstance(heater, dict):
                    normalized_heater = _normalize_water_heater(heater)
                    normalized_heaters.append(normalized_heater)
                else:
                    normalized_heaters.append(heater)
            plumbing["water_heaters"] = normalized_heaters

    # Normalize piping data
    piping = plumbing.get("piping")
    if isinstance(piping, list):
        normalized_piping = []
        for pipe in piping:
            if isinstance(pipe, dict):
                normalized_pipe = _normalize_pipe(pipe)
                normalized_piping.append(normalized_pipe)
            else:
                normalized_piping.append(pipe)
        plumbing["piping"] = normalized_piping

    return parsed_json


def _normalize_plumbing_fixture(fixture: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize keys and values for a plumbing fixture."""
    if not isinstance(fixture, dict):
        return fixture

    normalized = fixture.copy()

    # Map of preferred key names to potential synonyms
    synonyms_map = {
        "fixture_id": [
            "id",
            "mark",
            "tag",
            "fixture_tag",
            "fixture_number",
            "number",
            "fixture_identifier",
            "code",
            "fixture_code",
            "plumbing_fixture_id",
            "item_number",
            "ref",
            "reference",
            "p_id",
            "p-id",
            "plumbing_id",
            "designation",
            "fixture_mark",
        ],
        "description": [
            "name",
            "fixture",
            "type",
            "fixture_type",
            "item",
            "fixture_name",
            "description_name",
            "fixture_desc",
            "text",
            "specification",
            "desc",
            "item_desc",
            "item_description",
            "device",
            "fixture_device",
            "product",
            "plumbing_fixture",
        ],
        "manufacturer": [
            "mfr",
            "manufacturer",
            "make",
            "brand",
            "supplier",
            "vendor",
            "mfg",
            "producer",
            "company",
            "manufactured_by",
            "provided_by",
            "source",
            "maker",
            "distributor",
            "supply_company",
            "producer_name",
            "fabricator",
        ],
        "model": [
            "model_number",
            "catalog",
            "cat",
            "model_no",
            "part",
            "part_number",
            "part_no",
            "product_number",
            "product_no",
            "catalog_number",
            "catalog_no",
            "cat_no",
            "catalogue",
            "selection",
            "sku",
            "item_code",
            "model_name",
            "product_id",
        ],
        "flow_rate": [
            "flow",
            "gpm",
            "gpm_flow",
            "flow_gpm",
            "water_flow",
            "rate",
            "flow_rate_gpm",
            "gallons_per_minute",
            "gallon_rate",
            "flow_capacity",
            "capacity_gpm",
            "water_consumption",
            "consumption_rate",
            "flowrate",
            "fluid_flow",
            "water_usage",
            "usage_gpm",
        ],
        "connection_size": [
            "size",
            "conn_size",
            "pipe_size",
            "connection",
            "conn",
            "connection_diameter",
            "inlet_size",
            "outlet_size",
            "fitting_size",
            "coupling_size",
            "pipe_connection",
            "connect_size",
            "line_size",
            "diameter",
            "supply_size",
            "drain_size",
            "waste_size",
        ],
        "mounting": [
            "mount",
            "mounting_type",
            "installation",
            "install",
            "mounted",
            "placement",
            "support",
            "fixing",
            "attachment",
            "fixture_mount",
            "support_type",
            "install_method",
            "positioning",
            "mounting_method",
            "mounting_location",
            "setting",
            "placement_type",
            "setup",
        ],
    }

    # Normalize each field
    for target_key, possible_synonyms in synonyms_map.items():
        for key in list(normalized.keys()):
            if key in possible_synonyms or key.lower() in possible_synonyms:
                # Found a synonym, move to the preferred key
                if key != target_key:
                    normalized[target_key] = normalized.pop(key)

    # Special handling for flow rate (convert to numeric)
    if "flow_rate" in normalized and isinstance(normalized["flow_rate"], str):
        normalized["flow_rate"] = _extract_numeric_value(normalized["flow_rate"])

    return normalized


def _normalize_water_heater(heater: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize keys and values for a water heater."""
    if not isinstance(heater, dict):
        return heater

    normalized = heater.copy()

    # Map of preferred key names to potential synonyms
    synonyms_map = {
        "heater_id": [
            "id",
            "mark",
            "tag",
            "heater_tag",
            "water_heater_id",
            "wh_id",
            "whid",
            "heater_number",
            "heater_no",
            "water_heater_no",
            "wh_tag",
            "water_heater_tag",
            "unit_id",
            "unit_number",
            "wh",
            "hw",
            "dhw_id",
            "hw_heater_id",
            "hot_water_id",
        ],
        "capacity": [
            "size",
            "gallons",
            "tank_size",
            "volume",
            "capacity_gallons",
            "tank_volume",
            "tank_capacity",
            "gal",
            "gal_capacity",
            "storage",
            "storage_capacity",
            "water_capacity",
            "tank_gallons",
            "tank_gal",
            "storage_volume",
            "storage_gal",
            "volume_gallons",
        ],
        "input": [
            "btu",
            "input_btu",
            "btuh",
            "heat_input",
            "input_rate",
            "btu_input",
            "btu_hr",
            "btuh_input",
            "input_btuh",
            "heating_input",
            "thermal_input",
            "energy_input",
            "power_input",
            "input_power",
            "thermal_power",
            "heating_capacity",
            "input_capacity",
            "energy_rate",
        ],
        "output": [
            "output_btu",
            "btuh_output",
            "heat_output",
            "output_rate",
            "btu_output",
            "output_btuh",
            "heating_output",
            "thermal_output",
            "energy_output",
            "power_output",
            "output_power",
            "output_capacity",
            "delivered_heat",
            "delivered_btuh",
            "output_heat",
            "heat_delivery",
        ],
        "efficiency": [
            "ef",
            "energy_factor",
            "efficiency_factor",
            "thermal_efficiency",
            "energy_efficiency",
            "heat_efficiency",
            "performance",
            "performance_factor",
            "cop",
            "coefficient",
            "efficiency_rating",
            "energy_star_rating",
            "percent_efficiency",
            "operating_efficiency",
            "heater_efficiency",
        ],
        "recovery": [
            "recovery_rate",
            "gph",
            "recovery_gph",
            "gallons_per_hour",
            "gal_per_hour",
            "reheat_rate",
            "reheat_capacity",
            "recovery_capacity",
            "heat_recovery",
            "recovery_gallons",
            "hourly_recovery",
            "hour_recovery",
            "gph_recovery",
            "recovery_time",
            "heating_recovery",
            "recharge_rate",
        ],
        "fuel_type": [
            "fuel",
            "energy",
            "energy_source",
            "power_source",
            "source",
            "fuel_source",
            "power",
            "energy_type",
            "heating_source",
            "power_type",
            "heating_fuel",
            "utility",
            "utility_type",
            "fuel_supply",
            "energy_supply",
            "heating_medium",
            "input_type",
            "energy_input_type",
        ],
    }

    # Normalize each field
    for target_key, possible_synonyms in synonyms_map.items():
        for key in list(normalized.keys()):
            if key in possible_synonyms or key.lower() in possible_synonyms:
                # Found a synonym, move to the preferred key
                if key != target_key:
                    normalized[target_key] = normalized.pop(key)

    # Convert numeric fields to standard format
    numeric_fields = ["capacity", "input", "output", "efficiency", "recovery"]
    for field in numeric_fields:
        if field in normalized and isinstance(normalized[field], str):
            normalized[field] = _extract_numeric_value(normalized[field])

    return normalized


def _normalize_pipe(pipe: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize keys and values for piping data."""
    if not isinstance(pipe, dict):
        return pipe

    normalized = pipe.copy()

    # Map of preferred key names to potential synonyms
    synonyms_map = {
        "pipe_id": [
            "id",
            "mark",
            "tag",
            "label",
            "pipe_tag",
            "line_id",
            "line_number",
            "pipe_number",
            "pipeline_id",
            "system_id",
            "pipe_line",
            "line_tag",
            "service_id",
            "utility_id",
            "reference",
            "piping_id",
            "pipe_designation",
            "identifier",
        ],
        "service": [
            "system",
            "use",
            "utility",
            "function",
            "purpose",
            "application",
            "service_type",
            "usage",
            "fluid",
            "contents",
            "fluid_type",
            "medium",
            "pipe_service",
            "pipe_use",
            "pipe_contents",
            "pipe_medium",
            "pipe_function",
            "fluid_service",
            "line_service",
            "content_type",
        ],
        "material": [
            "pipe_material",
            "type",
            "material_type",
            "composition",
            "construct",
            "material_spec",
            "spec",
            "pipe_type",
            "material_grade",
            "grade",
            "pipe_spec",
            "pipe_composition",
            "construction",
            "material_construction",
            "make",
            "material_make",
            "substance",
            "pipe_substance",
        ],
        "size": [
            "diameter",
            "pipe_size",
            "nominal_size",
            "nom_size",
            "line_size",
            "diameter_size",
            "dn",
            "nps",
            "nominal_pipe_size",
            "nom_diameter",
            "pipe_diameter",
            "nom_pipe_size",
            "diameter_inches",
            "diameter_mm",
            "size_in",
            "size_mm",
            "dim",
            "dimension",
        ],
        "insulation": [
            "insul",
            "insulation_type",
            "pipe_insulation",
            "thermal_insulation",
            "covering",
            "wrap",
            "insul_type",
            "insul_material",
            "insulation_material",
            "thermal_wrap",
            "thermal_covering",
            "heat_insulation",
            "cold_insulation",
            "jacket",
            "pipe_jacket",
            "lagging",
            "thermal_jacket",
        ],
        "insulation_thickness": [
            "insul_thickness",
            "insulation_size",
            "thickness",
            "insul_size",
            "covering_thickness",
            "wrap_thickness",
            "jacket_thickness",
            "insulation_depth",
            "lagging_thickness",
            "insul_depth",
            "covering_size",
            "thermal_thickness",
            "insul_dimension",
            "insulation_dim",
            "ins_thickness",
        ],
        "pressure_rating": [
            "pressure",
            "rating",
            "class",
            "pressure_class",
            "psi",
            "max_pressure",
            "working_pressure",
            "design_pressure",
            "pressure_spec",
            "pressure_grade",
            "pressure_capacity",
            "maximum_psi",
            "pressure_psi",
            "pipe_class",
            "pipe_rating",
            "pressure_rating_psi",
            "operating_pressure",
            "service_pressure",
        ],
    }

    # Normalize each field
    for target_key, possible_synonyms in synonyms_map.items():
        for key in list(normalized.keys()):
            if key in possible_synonyms or key.lower() in possible_synonyms:
                # Found a synonym, move to the preferred key
                if key != target_key:
                    normalized[target_key] = normalized.pop(key)

    # Convert size to numeric when possible
    if "size" in normalized and isinstance(normalized["size"], str):
        normalized["size"] = _extract_pipe_size(normalized["size"])

    return normalized


def _extract_numeric_value(value_str: str) -> float:
    """Extract numeric value from a string, handling common units."""
    if not isinstance(value_str, str):
        return value_str

    # Remove non-numeric characters except decimals
    numeric_chars = re.sub(r"[^\d.]", "", value_str)

    # Return as float if possible
    try:
        if numeric_chars:
            return float(numeric_chars)
    except ValueError:
        pass

    return value_str


def _extract_pipe_size(size_str: str) -> str:
    """
    Extract pipe size, preserving fractions for common plumbing sizes.
    Examples: "1/2\"", "3/4 inch", "1-1/2\""
    """
    if not isinstance(size_str, str):
        return size_str

    # Common pipe fraction sizes
    fraction_map = {
        "1/8": 0.125,
        "1/4": 0.25,
        "3/8": 0.375,
        "1/2": 0.5,
        "5/8": 0.625,
        "3/4": 0.75,
        "7/8": 0.875,
        "1-1/4": 1.25,
        "1-1/2": 1.5,
        "2-1/2": 2.5,
        "3-1/2": 3.5,
    }

    # Try to match common fraction patterns
    for fraction, decimal in fraction_map.items():
        if fraction in size_str:
            return decimal

    # Try to extract standard numeric
    numeric = _extract_numeric_value(size_str)
    if isinstance(numeric, (int, float)):
        return numeric

    # Return original if no match
    return size_str
