# /Users/collin/Desktop/Ohmni/Projects/ohmni-oracle-template/utils/json_utils.py
import re
import json
import logging
import datetime  # Add this import for date/datetime handling
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that handles date and datetime objects by converting them to ISO format strings.
    Use with json.dumps(data, cls=DateTimeEncoder) to properly serialize dates.
    """

    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        return super().default(obj)


def repair_panel_json(json_str: str) -> str:
    """
    Attempt to repair common JSON syntax errors often found in
    AI-generated panel schedule responses.

    Args:
        json_str: String containing potentially malformed JSON

    Returns:
        Repaired JSON string, or original if repair heuristics don't apply or fail validation.
    """
    if not isinstance(json_str, str):
        logger.warning("repair_panel_json received non-string input, returning as is.")
        return json_str

    fixed = json_str
    # Attempt to fix missing commas between objects in an array (common issue)
    fixed = re.sub(r"}\s*{", "}, {", fixed)

    # Attempt to fix trailing commas before closing brackets/braces (strict JSON invalid)
    fixed = re.sub(r",\s*}", "}", fixed)
    fixed = re.sub(r",\s*\]", "]", fixed)

    # Attempt to fix missing quotes around keys (heuristic, might be imperfect)
    try:
        fixed = re.sub(r"([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'\1"\2":', fixed)
    except Exception as e:
        logger.warning(f"Regex error during key quoting repair: {e}")

    # Attempt to fix truncated JSON by adding missing closing brackets/braces
    open_braces = fixed.count("{")
    close_braces = fixed.count("}")
    open_brackets = fixed.count("[")
    close_brackets = fixed.count("]")

    if open_braces > close_braces:
        fixed += "}" * (open_braces - close_braces)
        logger.debug(f"Added {open_braces - close_braces} closing braces.")
    if open_brackets > close_brackets:
        fixed += "]" * (open_brackets - close_brackets)
        logger.debug(f"Added {open_brackets - close_brackets} closing brackets.")

    # Final validation check
    try:
        json.loads(fixed)
        if fixed != json_str:
            logger.info("JSON repair applied successfully.")
        return fixed
    except json.JSONDecodeError:
        logger.warning(
            "JSON repair attempt failed validation. Returning original string."
        )
        return json_str


def parse_json_safely(json_str: str, repair: bool = False) -> Optional[Dict[str, Any]]:
    """
    Parse JSON string with an optional fallback repair attempt.

    Args:
        json_str: JSON string to parse.
        repair: If True, attempt to repair the JSON string if initial parsing fails.

    Returns:
        Parsed JSON object (Dict) or None if parsing failed even after repair.
    """
    if not isinstance(json_str, str):
        logger.error("parse_json_safely received non-string input.")
        return None
    try:
        # Try standard parsing first
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning(
            f"Initial JSON parsing failed: {e}. Raw start: {json_str[:100]}..."
        )
        if repair:
            logger.info("Attempting JSON repair...")
            repaired_str = repair_panel_json(json_str)
            try:
                # Try parsing the repaired string
                parsed_obj = json.loads(repaired_str)
                logger.info("Successfully parsed repaired JSON.")
                return parsed_obj
            except json.JSONDecodeError as e2:
                # Still failed after repair attempt
                logger.error(f"JSON parsing failed even after repair attempt: {e2}")
                logger.error(f"Repaired string snippet: {repaired_str[:500]}...")
                return None
        else:
            # No repair requested, return None
            return None
    except Exception as ex:
        logger.error(f"Unexpected error during JSON parsing: {ex}")
        return None
