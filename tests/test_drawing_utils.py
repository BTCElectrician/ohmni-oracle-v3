"""
Test suite for drawing detection utilities.
"""
import os
import sys

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.drawing_utils import detect_drawing_info


def test_detect_drawing_info_architectural():
    """Test detection of architectural drawing types."""
    # Test floor plans
    main_type, subtype = detect_drawing_info("A1.0 FLOOR PLAN.pdf")
    assert main_type == "Architectural"
    assert subtype == "FloorPlan"

    # Test reflected ceiling plans
    main_type, subtype = detect_drawing_info("A2.1 REFLECTED CEILING PLAN.pdf")
    assert main_type == "Architectural"
    assert subtype == "ReflectedCeiling"

    # Test wall types
    main_type, subtype = detect_drawing_info("A5.1 WALL TYPES.pdf")
    assert main_type == "Architectural"
    assert subtype == "Wall"

    # Test door schedules
    main_type, subtype = detect_drawing_info("A6.1 DOOR SCHEDULE.pdf")
    assert main_type == "Architectural"
    assert subtype == "Door"

    # Test details
    main_type, subtype = detect_drawing_info("A7.2 DETAILS.pdf")
    assert main_type == "Architectural"
    assert subtype == "Detail"


def test_detect_drawing_info_electrical():
    """Test detection of electrical drawing types."""
    # Test panel schedules
    main_type, subtype = detect_drawing_info("E4.1 PANEL SCHEDULES.pdf")
    assert main_type == "Electrical"
    assert subtype == "PanelSchedule"

    # Test lighting plans
    main_type, subtype = detect_drawing_info("E2.1 LIGHTING PLAN.pdf")
    assert main_type == "Electrical"
    assert subtype == "Lighting"

    # Test power plans
    main_type, subtype = detect_drawing_info("E3.1 POWER PLAN.pdf")
    assert main_type == "Electrical"
    assert subtype == "Power"

    # Test risers
    main_type, subtype = detect_drawing_info("E5.1 RISER DIAGRAM.pdf")
    assert main_type == "Electrical"
    assert subtype == "Riser"

    # Test single line diagrams
    main_type, subtype = detect_drawing_info("E5.2 ONE LINE DIAGRAM.pdf")
    assert main_type == "Electrical"
    assert subtype == "Riser"


def test_detect_drawing_info_mechanical():
    """Test detection of mechanical drawing types."""
    # Test schedules
    main_type, subtype = detect_drawing_info("M5.1 EQUIPMENT SCHEDULES.pdf")
    assert main_type == "Mechanical"
    assert subtype == "Schedule"

    # Test ventilation
    main_type, subtype = detect_drawing_info("M2.1 VENTILATION PLAN.pdf")
    assert main_type == "Mechanical"
    assert subtype == "Ventilation"

    # Test piping
    main_type, subtype = detect_drawing_info("M3.1 PIPING DIAGRAM.pdf")
    assert main_type == "Mechanical"
    assert subtype == "Piping"


def test_detect_drawing_info_plumbing():
    """Test detection of plumbing drawing types."""
    # Test fixture schedules
    main_type, subtype = detect_drawing_info("P5.1 FIXTURE SCHEDULE.pdf")
    assert main_type == "Plumbing"
    assert subtype == "Fixture"

    # Test equipment schedules
    main_type, subtype = detect_drawing_info("P5.2 WATER HEATER SCHEDULE.pdf")
    assert main_type == "Plumbing"
    assert subtype == "Equipment"

    # Test piping
    main_type, subtype = detect_drawing_info("P3.1 PIPING PLAN.pdf")
    assert main_type == "Plumbing"
    assert subtype == "Pipe"


def test_detect_drawing_info_specifications():
    """Test detection of specification documents."""
    main_type, subtype = detect_drawing_info("SPECIFICATIONS.pdf")
    assert main_type == "Specifications"
    assert subtype == "Spec"

    main_type, subtype = detect_drawing_info("E0.1 ELECTRICAL SPEC.pdf")
    assert main_type == "Electrical"
    assert subtype == "Spec"


def test_detect_drawing_info_edge_cases():
    """Test edge cases for drawing detection."""
    # Empty filename
    main_type, subtype = detect_drawing_info("")
    assert main_type == "General"
    assert subtype is None

    # Filename with no clear type indicators
    main_type, subtype = detect_drawing_info("DRAWING.pdf")
    assert main_type == "General"
    assert subtype is None

    # Filename with multiple potential subtypes (should use first match)
    main_type, subtype = detect_drawing_info(
        "E4.1 PANEL SCHEDULES AND RISER DIAGRAMS.pdf"
    )
    assert main_type == "Electrical"
    assert subtype == "PanelSchedule"
