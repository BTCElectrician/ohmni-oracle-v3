import os
import re
from typing import Tuple, Optional


def detect_drawing_info(filename: str) -> Tuple[str, Optional[str]]:
    """
    Flexible drawing type detection for 80+ different drawings.
    Handles common discipline codes while remaining adaptable to unusual types.
    """
    if not filename:
        return "General", None

    filename_upper = os.path.basename(filename).upper()

    # Comprehensive discipline detection
    discipline_markers = {
        "A": "Architectural",
        "E": "Electrical",
        "M": "Mechanical",
        "P": "Plumbing",
        "C": "Civil",
        "S": "Structural",
        "T": "Technology",
        "FA": "FireAlarm",
        "FP": "FireProtection",
        "LV": "LowVoltage",
        "LD": "LowVoltage",
        "FS": "FoodService",
        "AV": "AudioVisual",
        "H": "HVAC",
        "I": "Interiors",
        "L": "Landscape",
        "TL": "Telecom",
        "SC": "Security",
        "ID": "InteriorDesign",
        "FD": "FireDetection",
        "ES": "EnvironmentalSystems",
        "LT": "Lighting",
        "TP": "TelephoneSystem",
        "EX": "Exhibit",
        "FE": "FireEgress",
        "SM": "SiteMechanical",
        "SE": "SiteElectrical",
        "Q": "Equipment",
    }

    # Check for two-letter codes first
    for prefix, discipline in discipline_markers.items():
        if len(prefix) == 2 and filename_upper.startswith(prefix):
            # Check for subtypes in electrical drawings
            if discipline == "Electrical" and any(
                term in filename_upper for term in ["PANEL", "SCHEDULE"]
            ):
                return discipline, "PANEL_SCHEDULE"
            # Check if low voltage drawings are fire alarm related
            if discipline == "LowVoltage" and any(
                term in filename_upper for term in ["FIRE", "ALARM", "SMOKE", "DETECTOR", "PULL", "STROBE", "HORN"]
            ):
                return "FireAlarm", "LOW_VOLTAGE"
            return discipline, None

    # Then check single letter codes
    for prefix, discipline in discipline_markers.items():
        if len(prefix) == 1 and filename_upper.startswith(prefix):
            # Check for subtypes in electrical drawings
            if discipline == "Electrical" and any(
                term in filename_upper for term in ["PANEL", "SCHEDULE"]
            ):
                return discipline, "PANEL_SCHEDULE"
            return discipline, None

    # For any unrecognized prefix, extract first letter/number as a fallback
    match = re.match(r"^([A-Z0-9]{1,2})", filename_upper)
    if match:
        prefix = match.group(1)
        return f"Type_{prefix}", None

    # Default fallback
    return "General", None
