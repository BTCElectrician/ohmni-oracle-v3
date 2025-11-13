"""
Plumbing normalization utilities.
Handles fixture schedules, water heater schedules, and piping schedules.
"""
import logging
from typing import Dict, Any

from .common import extract_numeric_value

logger = logging.getLogger(__name__)


def extract_pipe_size(size_str: str) -> str:
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
    numeric = extract_numeric_value(size_str)
    if isinstance(numeric, (int, float)):
        return numeric

    # Return original if no match
    return size_str


def normalize_plumbing_fixture(fixture: Dict[str, Any]) -> Dict[str, Any]:
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
        normalized["flow_rate"] = extract_numeric_value(normalized["flow_rate"])

    return normalized


def normalize_water_heater(heater: Dict[str, Any]) -> Dict[str, Any]:
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
            normalized[field] = extract_numeric_value(normalized[field])

    return normalized


def normalize_pipe(pipe: Dict[str, Any]) -> Dict[str, Any]:
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
        normalized["size"] = extract_pipe_size(normalized["size"])

    return normalized


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
                normalized_fixture = normalize_plumbing_fixture(fixture)
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
                    normalized_heater = normalize_water_heater(heater)
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
                normalized_pipe = normalize_pipe(pipe)
                normalized_piping.append(normalized_pipe)
            else:
                normalized_piping.append(pipe)
        plumbing["piping"] = normalized_piping

    return parsed_json

