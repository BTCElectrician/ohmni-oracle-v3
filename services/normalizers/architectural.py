"""
Architectural normalization utilities.
Handles room schedules, door schedules, window schedules, and room finish data.
"""
import logging
from typing import Dict, Any

from .common import safe_int, extract_numeric_value

logger = logging.getLogger(__name__)


def _normalize_room(room: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize keys for a room / space schedule entry."""
    if not isinstance(room, dict):
        return room

    normalized = room.copy()

    synonyms_map = {
        "room_id": [
            "id",
            "mark",
            "tag",
            "room_tag",
            "room_id",
            "space_id",
            "number",
            "room_number",
            "rm_no",
            "space_no",
        ],
        "name": [
            "name",
            "room_name",
            "space_name",
            "description",
            "desc",
            "label",
            "title",
        ],
        "level": [
            "level",
            "floor",
            "story",
            "storey",
            "level_name",
        ],
        "area_sf": [
            "area",
            "area_sqft",
            "area_sf",
            "sf",
            "sq_ft",
            "sqft",
        ],
        "occupancy": [
            "occ",
            "occupancy",
            "occupancy_type",
            "use",
            "usage",
            "program",
        ],
        "comments": [
            "comments",
            "comment",
            "notes",
            "note",
            "remark",
            "remarks",
        ],
    }

    for target_key, possible_synonyms in synonyms_map.items():
        for key in list(normalized.keys()):
            if key in possible_synonyms or key.lower() in possible_synonyms:
                if key != target_key:
                    normalized[target_key] = normalized.pop(key)

    # Normalize area to a numeric value when possible
    if "area_sf" in normalized:
        value = normalized["area_sf"]
        numeric = extract_numeric_value(str(value)) if not isinstance(value, (int, float)) else value
        try:
            if isinstance(numeric, str):
                numeric = float(numeric) if numeric else None
            if isinstance(numeric, (int, float)):
                normalized["area_sf"] = numeric
        except Exception:
            # Leave as-is if parsing fails
            pass

    return normalized


def _normalize_door(door: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize keys for a door schedule entry."""
    if not isinstance(door, dict):
        return door

    normalized = door.copy()

    synonyms_map = {
        "door_id": [
            "id",
            "mark",
            "tag",
            "door",
            "door_mark",
            "door_number",
            "number",
            "opening",
            "opening_mark",
        ],
        "type": [
            "type",
            "door_type",
            "leaf_type",
            "assembly_type",
            "family",
            "family_type",
        ],
        "width": [
            "width",
            "w",
            "door_width",
            "frame_width",
            "clear_width",
        ],
        "height": [
            "height",
            "h",
            "door_height",
            "frame_height",
            "clear_height",
        ],
        "frame_material": [
            "frame",
            "frame_material",
            "jamb",
            "frame_type",
            "frame_finish",
        ],
        "door_material": [
            "material",
            "door_material",
            "leaf_material",
            "leaf",
            "panel",
            "door_finish",
        ],
        "fire_rating": [
            "fire",
            "fire_rating",
            "rating",
            "fr",
            "fire_protection",
            "fire_label",
        ],
        "sound_rating": [
            "stc",
            "sound",
            "sound_rating",
            "acoustic_rating",
            "acoustical_rating",
        ],
        "handing": [
            "hand",
            "handing",
            "swing",
            "door_swing",
            "door_hand",
        ],
        "comments": [
            "comments",
            "comment",
            "notes",
            "note",
            "remark",
            "remarks",
        ],
    }

    for target_key, possible_synonyms in synonyms_map.items():
        for key in list(normalized.keys()):
            if key in possible_synonyms or key.lower() in possible_synonyms:
                if key != target_key:
                    normalized[target_key] = normalized.pop(key)

    # Width/height often come as strings like "3'-0\"" or "7'-0\""
    for dim_key in ("width", "height"):
        if dim_key in normalized:
            value = normalized[dim_key]
            numeric = extract_numeric_value(str(value)) if not isinstance(value, (int, float)) else value
            try:
                if isinstance(numeric, str):
                    numeric = float(numeric) if numeric else None
                if isinstance(numeric, (int, float)):
                    normalized[dim_key] = numeric
            except Exception:
                pass

    return normalized


def _normalize_window(window: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize keys for a window schedule entry."""
    if not isinstance(window, dict):
        return window

    normalized = window.copy()

    synonyms_map = {
        "window_id": [
            "id",
            "mark",
            "tag",
            "window",
            "window_mark",
            "window_number",
            "number",
            "opening",
        ],
        "type": [
            "type",
            "window_type",
            "assembly_type",
            "family",
            "family_type",
        ],
        "width": [
            "width",
            "w",
            "window_width",
            "clear_width",
        ],
        "height": [
            "height",
            "h",
            "window_height",
            "clear_height",
        ],
        "glazing": [
            "glass",
            "glazing",
            "glass_type",
            "pane",
            "glass_spec",
        ],
        "frame_material": [
            "frame",
            "frame_material",
            "frame_type",
            "frame_finish",
        ],
        "u_value": [
            "u",
            "u_value",
            "u-factor",
            "ufactor",
            "u_factor",
        ],
        "shgc": [
            "shgc",
            "solar_heat_gain",
            "solar_heat_gain_coeff",
            "solar_heat_gain_coefficient",
        ],
        "comments": [
            "comments",
            "comment",
            "notes",
            "note",
            "remark",
            "remarks",
        ],
    }

    for target_key, possible_synonyms in synonyms_map.items():
        for key in list(normalized.keys()):
            if key in possible_synonyms or key.lower() in possible_synonyms:
                if key != target_key:
                    normalized[target_key] = normalized.pop(key)

    # Numeric window dimensions and performance
    for dim_key in ("width", "height", "u_value", "shgc"):
        if dim_key in normalized:
            value = normalized[dim_key]
            numeric = extract_numeric_value(str(value)) if not isinstance(value, (int, float)) else value
            try:
                if isinstance(numeric, str):
                    numeric = float(numeric) if numeric else None
                if isinstance(numeric, (int, float)):
                    normalized[dim_key] = numeric
            except Exception:
                pass

    return normalized


def _normalize_finish(finish: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize keys for a room finish schedule entry."""
    if not isinstance(finish, dict):
        return finish

    normalized = finish.copy()

    synonyms_map = {
        "room_id": [
            "room_id",
            "space_id",
            "room",
            "room_number",
            "space",
            "number",
            "mark",
            "tag",
        ],
        "name": [
            "name",
            "room_name",
            "space_name",
            "description",
            "desc",
        ],
        "floor_finish": [
            "floor",
            "floor_finish",
            "finish_floor",
            "flooring",
            "flr",
        ],
        "base_finish": [
            "base",
            "base_finish",
            "baseboard",
            "bse",
        ],
        "wall_finish": [
            "wall",
            "wall_finish",
            "walls",
            "wall_finishes",
            "w",
        ],
        "ceiling_finish": [
            "ceiling",
            "ceiling_finish",
            "ceil",
            "clg",
        ],
        "comments": [
            "comments",
            "comment",
            "notes",
            "note",
            "remark",
            "remarks",
        ],
    }

    for target_key, possible_synonyms in synonyms_map.items():
        for key in list(normalized.keys()):
            if key in possible_synonyms or key.lower() in possible_synonyms:
                if key != target_key:
                    normalized[target_key] = normalized.pop(key)

    return normalized


def normalize_architectural_schedule(parsed_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize architectural schedule fields with consistent naming.
    Handles:
    - Room / space schedules
    - Door schedules
    - Window schedules
    - Room finish schedules
    """
    if not isinstance(parsed_json, dict):
        logger.warning("Expected dict at top-level for architectural normalization.")
        return parsed_json

    architectural = parsed_json.get("ARCHITECTURAL")
    if not isinstance(architectural, dict):
        # No architectural data found
        return parsed_json

    # ---- Room / space schedule ----
    rooms = (
        architectural.get("rooms")
        or architectural.get("ROOMS")
        or architectural.get("room_schedule")
        or architectural.get("ROOM_SCHEDULE")
        or architectural.get("room_schedules")
    )
    if isinstance(rooms, list):
        normalized_rooms = []
        for room in rooms:
            if isinstance(room, dict):
                normalized_rooms.append(_normalize_room(room))
            else:
                normalized_rooms.append(room)
        architectural["rooms"] = normalized_rooms

    # ---- Door schedule ----
    doors = (
        architectural.get("doors")
        or architectural.get("DOORS")
        or architectural.get("door_schedule")
        or architectural.get("DOOR_SCHEDULE")
        or architectural.get("door_schedules")
    )
    if isinstance(doors, list):
        normalized_doors = []
        for door in doors:
            if isinstance(door, dict):
                normalized_doors.append(_normalize_door(door))
            else:
                normalized_doors.append(door)
        architectural["doors"] = normalized_doors

    # ---- Window schedule ----
    windows = (
        architectural.get("windows")
        or architectural.get("WINDOWS")
        or architectural.get("window_schedule")
        or architectural.get("WINDOW_SCHEDULE")
        or architectural.get("window_schedules")
    )
    if isinstance(windows, list):
        normalized_windows = []
        for window in windows:
            if isinstance(window, dict):
                normalized_windows.append(_normalize_window(window))
            else:
                normalized_windows.append(window)
        architectural["windows"] = normalized_windows

    # ---- Room finish schedule ----
    finishes = (
        architectural.get("finishes")
        or architectural.get("FINISHES")
        or architectural.get("finish_schedule")
        or architectural.get("FINISH_SCHEDULE")
        or architectural.get("room_finishes")
        or architectural.get("ROOM_FINISH_SCHEDULE")
    )
    if isinstance(finishes, list):
        normalized_finishes = []
        for finish in finishes:
            if isinstance(finish, dict):
                normalized_finishes.append(_normalize_finish(finish))
            else:
                normalized_finishes.append(finish)
        architectural["finishes"] = normalized_finishes

    return parsed_json


