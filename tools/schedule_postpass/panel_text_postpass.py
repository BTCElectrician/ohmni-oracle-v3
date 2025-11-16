"""
Panel text post-pass for filling missing even-numbered circuits.

Uses SCHEDULE_MODEL to extract all circuits from raw sheet text and fill/replace
panel circuit arrays in structured JSON.
"""
import re
import logging
from typing import Dict, Any, Optional
from openai import AsyncOpenAI

from config.settings import SCHEDULE_MODEL, LARGE_MODEL_TEMP, LARGE_MODEL_MAX_TOKENS
from services.ai_service import make_chat_completion_request
from utils.json_utils import parse_json_safely

logger = logging.getLogger(__name__)

PANEL_RE = re.compile(r"Panel:\s*([A-Za-z0-9.\-]+)", re.IGNORECASE)


def is_panel_schedule_sheet(sheet_json: Dict[str, Any]) -> bool:
    """
    Determine if sheet_json contains panel schedule data.
    
    Args:
        sheet_json: Parsed JSON structure
        
    Returns:
        True if this appears to be a panel schedule sheet
    """
    if not isinstance(sheet_json, dict):
        return False
    
    electrical = sheet_json.get("ELECTRICAL")
    if not isinstance(electrical, dict):
        return False
    
    # Check for panels list
    panels = electrical.get("panels")
    if isinstance(panels, list) and len(panels) > 0:
        return True
    
    # Check for PANEL_SCHEDULES
    panel_schedules = electrical.get("PANEL_SCHEDULES")
    if panel_schedules is not None:
        if isinstance(panel_schedules, dict) and len(panel_schedules) > 0:
            return True
        if isinstance(panel_schedules, list) and len(panel_schedules) > 0:
            return True
    
    # Check drawing title
    drawing_meta = sheet_json.get("DRAWING_METADATA", {})
    title = str(drawing_meta.get("title", "")).upper()
    if "PANEL" in title and "SCHEDULE" in title:
        return True
    
    return False


async def fill_panels_from_sheet_text(
    sheet_json: Dict[str, Any],
    sheet_text: str,
    client: AsyncOpenAI,
) -> Dict[str, Any]:
    """
    Use SCHEDULE_MODEL to extract all circuits for each panel from raw sheet text,
    and fill/replace ELECTRICAL.panels[*].circuits or PANEL_SCHEDULES[*].circuit_details.
    
    Returns a modified copy of sheet_json.
    
    Args:
        sheet_json: Structured JSON with ELECTRICAL section
        sheet_text: Raw text content from extraction (should contain Panel: markers)
        client: OpenAI async client for API calls
        
    Returns:
        Modified copy of sheet_json with circuits filled/replaced
    """
    if not isinstance(sheet_json, dict):
        logger.warning("[panel_text_postpass] sheet_json is not a dict, skipping")
        return sheet_json
    
    if not isinstance(sheet_text, str) or not sheet_text.strip():
        logger.warning("[panel_text_postpass] sheet_text is empty, skipping")
        return sheet_json
    
    electrical = sheet_json.get("ELECTRICAL")
    if not isinstance(electrical, dict):
        logger.warning("[panel_text_postpass] No ELECTRICAL section found, skipping")
        return sheet_json
    
    # Find all panel blocks in sheet_text
    matches = list(PANEL_RE.finditer(sheet_text))
    if not matches:
        logger.debug("[panel_text_postpass] No Panel: markers found in sheet_text")
        return sheet_json
    
    logger.info(f"[panel_text_postpass] Found {len(matches)} panel markers in sheet text")
    
    # Build panel blocks by slicing between matches
    panel_blocks = []
    for i, match in enumerate(matches):
        panel_name = match.group(1)
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(sheet_text)
        panel_block_text = sheet_text[start:end]
        panel_blocks.append((panel_name, panel_block_text))
    
    # Create a copy to modify
    result_json = _deep_copy_dict(sheet_json)
    result_electrical = result_json.setdefault("ELECTRICAL", {})
    
    # Process each panel block
    for panel_name, panel_block_text in panel_blocks:
        try:
            # Call model to extract circuits
            circuits_json = await _extract_circuits_from_panel_text(
                panel_name, panel_block_text, client
            )
            
            if not circuits_json or not isinstance(circuits_json, dict):
                logger.warning(
                    f"[panel_text_postpass] panel {panel_name}: invalid model response, skipping"
                )
                continue
            
            circuits = circuits_json.get("circuits", [])
            if not isinstance(circuits, list):
                logger.warning(
                    f"[panel_text_postpass] panel {panel_name}: circuits is not a list, skipping"
                )
                continue
            
            # Count existing circuits before update
            existing_count = _count_existing_circuits(result_electrical, panel_name)
            
            # Update the panel's circuits
            _update_panel_circuits(result_electrical, panel_name, circuits)
            
            # Log metrics
            logger.info(
                f"[panel_text_postpass] panel {panel_name}: model_circuits={len(circuits)}, "
                f"existing_circuits={existing_count}"
            )
            
        except Exception as e:
            logger.warning(
                f"[panel_text_postpass] panel {panel_name}: error processing panel: {e}",
                exc_info=True
            )
            continue
    
    return result_json


async def _extract_circuits_from_panel_text(
    panel_name: str,
    panel_block_text: str,
    client: AsyncOpenAI,
) -> Optional[Dict[str, Any]]:
    """
    Call SCHEDULE_MODEL to extract circuits from a single panel's text block.
    
    Args:
        panel_name: Name of the panel (e.g., "K1", "L1-20")
        panel_block_text: Raw text for this panel
        client: OpenAI async client
        
    Returns:
        Parsed JSON dict with "panel_name" and "circuits" list, or None on error
    """
    prompt = f"""You are extracting circuits from an electrical panel schedule.

Here is the raw text for a single panel:

{panel_block_text}

Return JSON with one object per circuit (not per row), like:

{{
  "panel_name": "{panel_name}",
  "circuits": [
    {{
      "circuit_number": 1,
      "load_name": "SLUSHIE MACHINE",
      "trip_amps": 20,
      "is_spare_or_space": false
    }},
    {{
      "circuit_number": 2,
      "load_name": "SPACE",
      "trip_amps": null,
      "is_spare_or_space": true
    }}
  ]
}}

Rules:
- Use the circuit numbers that appear in the text (e.g., 1-84).
- Include ALL circuits, including "SPARE" or "SPACE".
- If a row contains two circuits (odd on the left, even on the right), return two separate circuit objects.
- Ignore panel totals, enclosure/rating, and footnotes.
- Do not invent extra circuits; only output circuits that clearly exist in the text.
- Return ONLY valid JSON, no markdown, no code fences."""
    
    try:
        response_text = await make_chat_completion_request(
            client=client,
            input_text=prompt,
            model=SCHEDULE_MODEL,
            temperature=LARGE_MODEL_TEMP,
            max_tokens=min(LARGE_MODEL_MAX_TOKENS, 16384),  # Limit for panel circuits
            file_path=None,
            drawing_type="Electrical",
            instructions=None,
        )
        
        # Parse JSON with repair fallback
        parsed = parse_json_safely(response_text, repair=True)
        return parsed
        
    except Exception as e:
        logger.error(
            f"[panel_text_postpass] panel {panel_name}: model call failed: {e}",
            exc_info=True
        )
        return None


def _count_existing_circuits(electrical: Dict[str, Any], panel_name: str) -> int:
    """
    Count existing circuits for a panel in the electrical structure.
    
    Args:
        electrical: ELECTRICAL section dict
        panel_name: Panel name to find
        
    Returns:
        Count of existing circuits
    """
    # Check panels list
    panels = electrical.get("panels", [])
    if isinstance(panels, list):
        for panel in panels:
            if not isinstance(panel, dict):
                continue
            pname = _get_panel_name(panel)
            if pname and pname.upper() == panel_name.upper():
                circuits = panel.get("circuits") or panel.get("circuit_details", [])
                if isinstance(circuits, list):
                    return len([c for c in circuits if isinstance(c, dict) and c.get("circuit_number") is not None])
    
    # Check PANEL_SCHEDULES dict
    panel_schedules = electrical.get("PANEL_SCHEDULES")
    if isinstance(panel_schedules, dict):
        for pname, pdata in panel_schedules.items():
            if pname.upper() == panel_name.upper() and isinstance(pdata, dict):
                circuits = pdata.get("circuit_details") or pdata.get("circuits", [])
                if isinstance(circuits, list):
                    return len([c for c in circuits if isinstance(c, dict) and c.get("circuit_number") is not None])
    
    # Check PANEL_SCHEDULES list
    if isinstance(panel_schedules, list):
        for panel in panel_schedules:
            if not isinstance(panel, dict):
                continue
            pname = _get_panel_name(panel)
            if pname and pname.upper() == panel_name.upper():
                circuits = panel.get("circuit_details") or panel.get("circuits", [])
                if isinstance(circuits, list):
                    return len([c for c in circuits if isinstance(c, dict) and c.get("circuit_number") is not None])
    
    return 0


def _update_panel_circuits(
    electrical: Dict[str, Any],
    panel_name: str,
    new_circuits: list,
) -> None:
    """
    Update a panel's circuits list in the electrical structure.
    Preserves existing metadata, only replaces circuits/circuit_details.
    
    Args:
        electrical: ELECTRICAL section dict (modified in place)
        panel_name: Panel name to update
        new_circuits: List of circuit dicts from model
    """
    # Normalize new circuits to expected format
    normalized_circuits = []
    for ckt in new_circuits:
        if not isinstance(ckt, dict):
            continue
        normalized = {
            "circuit_number": ckt.get("circuit_number"),
            "load_name": ckt.get("load_name"),
            "trip": ckt.get("trip_amps") or ckt.get("trip"),
            "poles": ckt.get("poles"),
            "load_classification": ckt.get("load_classification"),
            "phase_loads": ckt.get("phase_loads", {"A": None, "B": None, "C": None}),
        }
        # Handle spare/space
        if ckt.get("is_spare_or_space"):
            if not normalized["load_name"]:
                normalized["load_name"] = "SPARE" if not normalized.get("trip") else "SPACE"
        normalized_circuits.append(normalized)
    
    # Try to find and update in panels list
    panels = electrical.get("panels", [])
    if isinstance(panels, list):
        for panel in panels:
            if not isinstance(panel, dict):
                continue
            pname = _get_panel_name(panel)
            if pname and pname.upper() == panel_name.upper():
                panel["circuits"] = normalized_circuits
                logger.debug(f"[panel_text_postpass] Updated panel {panel_name} in panels list")
                return
    
    # Try PANEL_SCHEDULES dict
    panel_schedules = electrical.get("PANEL_SCHEDULES")
    if isinstance(panel_schedules, dict):
        for pname, pdata in panel_schedules.items():
            if pname.upper() == panel_name.upper() and isinstance(pdata, dict):
                pdata["circuit_details"] = normalized_circuits
                logger.debug(f"[panel_text_postpass] Updated panel {panel_name} in PANEL_SCHEDULES dict")
                return
    
    # Try PANEL_SCHEDULES list
    if isinstance(panel_schedules, list):
        for panel in panel_schedules:
            if not isinstance(panel, dict):
                continue
            pname = _get_panel_name(panel)
            if pname and pname.upper() == panel_name.upper():
                panel_data = panel.get("panel") or panel
                if isinstance(panel_data, dict):
                    panel_data["circuits"] = normalized_circuits
                    logger.debug(f"[panel_text_postpass] Updated panel {panel_name} in PANEL_SCHEDULES list")
                    return
    
    # If not found, create new entry in panels list
    logger.info(f"[panel_text_postpass] Panel {panel_name} not found, creating new entry")
    if not isinstance(panels, list):
        electrical["panels"] = []
        panels = electrical["panels"]
    
    panels.append({
        "panel_name": panel_name,
        "circuits": normalized_circuits,
    })


def _get_panel_name(panel: Dict[str, Any]) -> Optional[str]:
    """
    Extract panel name from a panel dict using common key variations.
    
    Args:
        panel: Panel dict
        
    Returns:
        Panel name string or None
    """
    for key in ["panel_name", "panel_id", "name", "panel", "id"]:
        value = panel.get(key)
        if value and isinstance(value, str):
            return value
    return None


def _deep_copy_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a deep copy of a dict (simple implementation for JSON-like structures).
    
    Args:
        d: Dict to copy
        
    Returns:
        Deep copy of dict
    """
    import json
    return json.loads(json.dumps(d))

