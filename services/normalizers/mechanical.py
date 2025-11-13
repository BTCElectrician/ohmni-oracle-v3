"""
Mechanical normalization utilities.
Handles equipment schedules, air devices, diffusers, and HVAC systems.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def get_equipment_type(equipment_item: Dict[str, Any]) -> str:
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
                equip_type = get_equipment_type(item)
                if equip_type not in equipment_by_type:
                    equipment_by_type[equip_type] = []
                equipment_by_type[equip_type].append(item)
        mechanical["equipment"] = equipment_by_type

    # Handle other mechanical schedules if needed
    # [Add more normalization logic for other mechanical subtypes as needed]

    return parsed_json

