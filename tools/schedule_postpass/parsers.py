"""Schedule post-pass parsing helpers."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def classify_schedule_block(block: Dict[str, Any]) -> str:
    """Map extractor metadata to a normalized schedule type."""
    t = (block.get("type") or "").lower()
    n = (block.get("name") or "").lower()
    s = (block.get("subtype") or "").lower()
    haystack = " ".join([t, n, s])

    if "panel" in haystack and "schedule" in haystack:
        return "panel"
    if "unit" in haystack and "schedule" in haystack:
        return "unit_plan"
    if "lighting" in haystack and "schedule" in haystack:
        return "lighting_fixture"

    if ("electrical equipment" in haystack or "single line" in haystack) and "schedule" in haystack:
        return "elec_equipment"
    if ("mechanical" in haystack or any(term in haystack for term in ("rtu", "ahu", "vfd"))) and "schedule" in haystack:
        return "mech_equipment"
    if ("plumbing" in haystack or any(term in haystack for term in ("ejector", "water heater", "wh"))) and "schedule" in haystack:
        return "plumb_equipment"

    if ("wall" in haystack or "partition" in haystack) and "schedule" in haystack:
        return "wall_partition"
    if "door" in haystack and "schedule" in haystack:
        return "door"
    if "ceiling" in haystack and "schedule" in haystack:
        return "ceiling"
    if "finish" in haystack and "schedule" in haystack:
        return "finish"
    return ""


def _get(row: Dict[str, Any], *keys: str, default: Optional[Any] = None) -> Optional[Any]:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return default


def _parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        stripped = str(value).lower().replace(",", "").replace("in", "").replace('"', "").strip()
        return float(stripped)
    except (ValueError, TypeError):
        return None


def extract_key(stype: str, row: Dict[str, Any]) -> Dict[str, Any]:
    if stype == "panel":
        panel = _get(row, "panel", "panel_name", "board")
        circuit = _get(row, "circuit", "ckt", "cct", "circuit_number")
        if panel and circuit:
            return {"panel": str(panel).strip(), "circuit": str(circuit).strip()}
        return {}

    if stype == "unit_plan":
        unit = _get(row, "unit", "unit_id", "room", "space")
        tag = _get(row, "tag", "device", "appliance", "equipment")
        if unit and tag:
            return {"unit": str(unit).strip(), "tag": str(tag).strip()}
        return {}

    if stype in {"elec_equipment", "mech_equipment", "plumb_equipment", "lighting_fixture"}:
        tag = _get(row, "tag", "equipment_tag", "name", "fixture_type", "type", "mark")
        return {"tag": str(tag).strip()} if tag else {}

    if stype == "wall_partition":
        wall_type = _get(row, "wall_type", "partition_type", "type")
        return {"wall_type": str(wall_type).strip()} if wall_type else {}

    if stype == "door":
        door = _get(row, "door_number", "mark", "door", "id")
        return {"door_number": str(door).strip()} if door else {}

    if stype == "ceiling":
        ceiling = _get(row, "ceiling_type", "type")
        return {"ceiling_type": str(ceiling).strip()} if ceiling else {}

    if stype == "finish":
        space = _get(row, "space", "room", "area", "name")
        return {"tag": str(space).strip()} if space else {}

    return {}


def extract_attributes(stype: str, row: Dict[str, Any]) -> Dict[str, Any]:
    attrs: Dict[str, Any] = {}

    attrs["description"] = _get(row, "description", "desc", "notes", "load")

    attrs["voltage"] = _parse_float(_get(row, "voltage", "volts", "v"))
    attrs["phase"] = _get(row, "phase", "ph")
    attrs["rating_a"] = _parse_float(_get(row, "amps", "amp", "a", "breaker", "breaker_a"))
    attrs["wire"] = _get(row, "wire", "conductor")
    attrs["conduit"] = _get(row, "conduit", "raceway")
    attrs["hp"] = _parse_float(_get(row, "hp"))
    attrs["kw"] = _parse_float(_get(row, "kw"))
    attrs["kva"] = _parse_float(_get(row, "kva"))
    attrs["mca"] = _parse_float(_get(row, "mca"))
    attrs["mop"] = _parse_float(_get(row, "mop"))
    attrs["fla"] = _parse_float(_get(row, "fla"))
    attrs["busbar_a"] = _parse_float(_get(row, "busbar_a"))
    attrs["disconnect"] = _get(row, "disconnect", "disc")
    attrs["panel"] = _get(row, "panel", "panel_name")
    attrs["circuit"] = _get(row, "circuit", "ckt", "cct")

    attrs["btu"] = _parse_float(_get(row, "btu"))
    attrs["gpm"] = _parse_float(_get(row, "gpm"))
    attrs["head"] = _parse_float(_get(row, "head"))

    attrs["fixture_type"] = _get(row, "fixture_type", "type", "mark")
    attrs["lumens"] = _parse_float(_get(row, "lumens", "lm"))
    attrs["lamp_type"] = _get(row, "lamp_type", "lamp")
    attrs["cct"] = _get(row, "cct")
    attrs["cri"] = _get(row, "cri")
    attrs["mounting"] = _get(row, "mounting", "mount")
    attrs["dimming"] = _get(row, "dimming")

    attrs["stc"] = _parse_float(_get(row, "stc"))
    attrs["fire_rating"] = _get(row, "fire_rating", "fr", "rating")
    attrs["stud_gauge"] = _get(row, "stud_gauge", "stud")
    attrs["layers"] = _get(row, "layers")
    attrs["ceiling_height_in"] = _parse_float(_get(row, "ceiling_height_in", "height", "ht"))
    attrs["acoustic"] = _get(row, "acoustic", "nrc")
    attrs["grid"] = _get(row, "grid")
    attrs["finish_floor"] = _get(row, "finish_floor", "floor_finish")
    attrs["finish_wall"] = _get(row, "finish_wall", "wall_finish")
    attrs["finish_ceiling"] = _get(row, "finish_ceiling", "ceiling_finish")
    attrs["hardware_set"] = _get(row, "hardware_set", "hw_set")
    attrs["size"] = _get(row, "size")
    attrs["material_frame"] = _get(row, "material_frame", "material", "frame")

    labels: List[str] = []
    description = (attrs.get("description") or "").lower()
    if "em" in description or "emergency" in description:
        labels.append("EM")
    if "gfci" in description:
        labels.append("GFCI")
    if "wp" in description or "weatherproof" in description:
        labels.append("WP")
    if "spare" in description:
        labels.append("Spare")
        attrs["is_spare"] = True
    if "space" in description:
        labels.append("Space")
        attrs["is_space"] = True

    if labels:
        attrs["_labels"] = list(set(labels))

    return {k: v for k, v in attrs.items() if v not in (None, "", [])}


def build_summary(stype: str, key: Dict[str, Any], attrs: Dict[str, Any]) -> str:
    """Create a compact, human-readable summary for fact docs."""
    try:
        if stype == "panel":
            rating = f"{int(attrs['rating_a'])}A" if attrs.get("rating_a") is not None else ""
            conduit = f", {attrs['conduit']}" if attrs.get("conduit") else ""
            return f"Panel {key.get('panel')} — Ckt {key.get('circuit')} — {attrs.get('description','').strip()} — {rating}{conduit}".strip(" —,")
        if stype == "unit_plan":
            volt = f"{int(attrs['voltage'])}V" if attrs.get("voltage") is not None else ""
            phase = f"/{attrs['phase']}φ" if attrs.get("phase") else ""
            rating = f", {int(attrs['rating_a'])}A" if attrs.get("rating_a") is not None else ""
            return f"Unit {key.get('unit')} — {key.get('tag')} — {volt}{phase}{rating}".strip(" —,")
        if stype == "mech_equipment":
            volt = f"{int(attrs['voltage'])}V" if attrs.get("voltage") is not None else ""
            phase = f"/{attrs['phase']}φ" if attrs.get("phase") else ""
            hp = f", {attrs['hp']}HP" if attrs.get("hp") is not None else ""
            kw = f" ({attrs['kw']}kW)" if attrs.get("kw") is not None else ""
            mca = f", MCA {attrs['mca']}" if attrs.get("mca") is not None else ""
            mop = f"/MOP {attrs['mop']}" if attrs.get("mop") is not None else ""
            return f"{key.get('tag')} — {volt}{phase}{hp}{kw}{mca}{mop}".strip(" —,")
        if stype == "lighting_fixture":
            volt = f"{int(attrs['voltage'])}V" if attrs.get("voltage") is not None else ""
            lumens = f", {int(attrs['lumens'])} lm" if attrs.get("lumens") is not None else ""
            return f"{key.get('tag') or attrs.get('fixture_type','Fixture')} — {volt}{lumens}".strip(" —,")
        if stype == "wall_partition":
            fire = attrs.get("fire_rating", "")
            stc = f", STC {int(attrs['stc'])}" if attrs.get("stc") is not None else ""
            return f"{key.get('wall_type')} — {fire}{stc}".strip(" —,")
        if stype == "door":
            hw = f", {attrs['hardware_set']}" if attrs.get("hardware_set") else ""
            fr = f", rating {attrs['fire_rating']}" if attrs.get("fire_rating") else ""
            return f"Door {key.get('door_number')}{hw}{fr}".strip(" —,")
        if stype == "ceiling":
            height = f"{attrs['ceiling_height_in']} in" if attrs.get("ceiling_height_in") is not None else ""
            return f"{key.get('ceiling_type')} — {height}".strip(" —,")
        if stype == "finish":
            return f"{key.get('tag','Space')} — floor {attrs.get('finish_floor','')}".strip(" —,")
        return "row"
    except Exception:
        return "row"


def build_template_summary(template_type: str, raw: Dict[str, Any]) -> str:
    """Generate the `content` summary for template docs."""
    room_id = raw.get("room_id") or raw.get("room_name", "Space")
    status = raw.get("template_status", "in_progress")

    if template_type == "electrical":
        parts: List[str] = []
        circuits = raw.get("circuits", {})
        lighting = circuits.get("lighting", [])
        if lighting:
            head = ", ".join(lighting[:3]) + ("..." if len(lighting) > 3 else "")
            parts.append(f"Lighting: {head}")
        outlets = raw.get("outlets", {})
        total_outlets = sum(outlets.get(key, 0) for key in ("regular_outlets", "controlled_outlets", "gfci_outlets", "usb_outlets"))
        if total_outlets:
            parts.append(f"{total_outlets} outlets")
        fire_alarm = raw.get("fire_alarm", {})
        fa_total = sum(fire_alarm.get(name, {}).get("count", 0) for name in ("smoke_detectors", "heat_detectors", "pull_stations", "horn_strobes"))
        if fa_total:
            parts.append(f"{fa_total} FA devices")
        data_tel = raw.get("data_telecom", {})
        if data_tel.get("data_outlets", 0):
            parts.append(f"{data_tel['data_outlets']} data")
        if raw.get("nurse_call", {}).get("stations", {}).get("count", 0):
            parts.append("nurse call")
        if raw.get("medical_gas", {}).get("oxygen", {}).get("count", 0):
            parts.append("medical gas")
        if raw.get("security", {}).get("cameras", {}).get("count", 0):
            parts.append("security")
        summary = f"{room_id} Electrical — " + ", ".join(parts) if parts else f"{room_id} Electrical (empty)"
        return f"{summary} ({status})"

    if template_type == "architectural":
        parts = []
        dims = raw.get("dimensions")
        ceiling = raw.get("ceiling_height")
        if dims:
            parts.append(f"Dims: {dims}")
        if ceiling:
            parts.append(f"Ceiling: {ceiling}")
        finishes = raw.get("finishes", {})
        floor = finishes.get("floor", {}).get("material")
        if floor:
            parts.append(f"Floor: {floor}")
        doors = raw.get("doors", {})
        door_count = doors.get("count", 0)
        if door_count:
            parts.append(f"{door_count} doors")
        special = raw.get("special_rooms", {})
        if special.get("clean_room", {}).get("classification"):
            parts.append("clean room")
        if special.get("lab", {}).get("fume_hood"):
            parts.append("lab")
        if special.get("operating_room", {}).get("or_number"):
            parts.append("OR")
        if raw.get("accessibility", {}).get("ada_required"):
            parts.append("ADA")
        summary = f"{room_id} Architectural — " + ", ".join(parts) if parts else f"{room_id} Architectural (empty)"
        return f"{summary} ({status})"

    return f"{room_id} Template ({template_type}) - Status: {status}"


def derive_template_tags(raw: Dict[str, Any]) -> List[str]:
    """Derive autosuggest tags from rich template payloads."""
    tags: List[str] = []

    circuits = raw.get("circuits", {})
    if circuits.get("lighting"):
        tags.append("lighting")
    if circuits.get("power"):
        tags.append("power")
    if circuits.get("emergency"):
        tags.append("emergency")
    if circuits.get("critical"):
        tags.append("critical")
    if circuits.get("ups"):
        tags.append("ups")

    outlets = raw.get("outlets", {})
    if outlets.get("regular_outlets", 0) or outlets.get("controlled_outlets", 0):
        tags.append("outlets")
    if outlets.get("gfci_outlets", 0):
        tags.append("gfci")
    if outlets.get("hospital_grade", 0):
        tags.append("hospital_grade")
    if outlets.get("red_outlets", 0):
        tags.append("emergency_power")

    if raw.get("mechanical_equipment"):
        tags.append("mechanical")
    if raw.get("appliances"):
        tags.append("appliances")

    fire_alarm = raw.get("fire_alarm", {})
    if any(fire_alarm.get(k, {}).get("count", 0) for k in ("smoke_detectors", "heat_detectors", "pull_stations", "horn_strobes")):
        tags.append("fire_alarm")

    data_tel = raw.get("data_telecom", {})
    if data_tel.get("data_outlets", 0):
        tags.append("data")
    if data_tel.get("wireless_ap"):
        tags.append("wireless")

    security = raw.get("security", {})
    if security.get("cameras", {}).get("count", 0):
        tags.append("security")
    if security.get("card_readers", {}).get("count", 0):
        tags.append("access_control")

    av = raw.get("audiovisual", {})
    if av.get("displays", {}).get("count", 0) or av.get("projectors", {}).get("count", 0):
        tags.append("audiovisual")

    if raw.get("nurse_call", {}).get("stations", {}).get("count", 0):
        tags.append("nurse_call")
    if raw.get("medical_gas", {}).get("oxygen", {}).get("count", 0):
        tags.append("medical_gas")
    if raw.get("medical_gas", {}).get("vacuum", {}).get("count", 0):
        tags.append("medical_vacuum")

    nurse = raw.get("nurse_call", {})
    if nurse.get("code_blue"):
        tags.append("code_blue")

    if raw.get("dimensions"):
        tags.append("dimensions")

    finishes = raw.get("finishes", {})
    if finishes:
        tags.append("finishes")

    doors = raw.get("doors", {})
    if doors.get("count", 0):
        tags.append("doors")
    if doors.get("fire_rated"):
        tags.append("fire_rated")

    if raw.get("accessibility", {}).get("ada_required"):
        tags.append("ada")
    if raw.get("fire_life_safety", {}).get("fire_rating_required"):
        tags.append("fire_rated")

    special = raw.get("special_rooms", {})
    if special.get("clean_room", {}).get("classification"):
        tags.append("clean_room")
    if special.get("lab", {}).get("fume_hood"):
        tags.append("lab")
    if special.get("operating_room", {}).get("or_number"):
        tags.append("operating_room")
    if special.get("data_center", {}).get("raised_floor"):
        tags.append("data_center")

    if raw.get("template_status") == "signed_off":
        tags.append("signed_off")

    if raw.get("discrepancies"):
        tags.append("has_discrepancies")

    deduped = {tag.lower() for tag in tags if tag}
    return sorted(deduped)
