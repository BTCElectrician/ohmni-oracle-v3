"""
Unit tests for panel column mapping functionality.
"""
import pytest
from utils.minimal_panel_clip import map_values_to_columns, detect_column_headers
import fitz


def test_column_mapping_within_tolerance():
    """Test that values are correctly assigned to columns within tolerance."""
    headers = {
        "CKT": 100.0,
        "LOAD_NAME": 200.0,
        "TRIP": 300.0,
    }
    
    # Simulate word tuples: (x0, y0, x1, y1, text, ...)
    words = [
        (95.0, 50.0, 105.0, 60.0, "1", 0, 0, 0),  # CKT column (within 30pt tolerance)
        (195.0, 50.0, 205.0, 60.0, "Light", 0, 0, 0),  # LOAD_NAME column
        (295.0, 50.0, 305.0, 60.0, "20", 0, 0, 0),  # TRIP column
        (98.0, 70.0, 102.0, 80.0, "3", 0, 0, 0),  # Next row, CKT
        (198.0, 70.0, 202.0, 80.0, "Fan", 0, 0, 0),  # LOAD_NAME
        (298.0, 70.0, 302.0, 80.0, "15", 0, 0, 0),  # TRIP
    ]
    
    mapped = map_values_to_columns(words, headers, tolerance=30.0)
    
    assert len(mapped) == 2
    assert mapped[0]["CKT"] == "1"
    assert mapped[0]["LOAD_NAME"] == "Light"
    assert mapped[0]["TRIP"] == "20"
    assert mapped[1]["CKT"] == "3"
    assert mapped[1]["LOAD_NAME"] == "Fan"
    assert mapped[1]["TRIP"] == "15"


def test_column_mapping_beyond_tolerance():
    """Test that values beyond tolerance are not mis-assigned."""
    headers = {
        "CKT": 100.0,
        "LOAD_NAME": 200.0,
        "TRIP": 300.0,
    }
    
    # Word that's too far from any column (beyond 30pt tolerance)
    words = [
        (150.0, 50.0, 160.0, 60.0, "Orphan", 0, 0, 0),  # Between CKT and LOAD_NAME, but >30pt from both
    ]
    
    mapped = map_values_to_columns(words, headers, tolerance=30.0)
    
    # Should create a row but not assign the orphan word to any column
    assert len(mapped) == 1
    # The orphan word should not appear in any column
    assert "CKT" not in mapped[0] or mapped[0].get("CKT") != "Orphan"
    assert "LOAD_NAME" not in mapped[0] or mapped[0].get("LOAD_NAME") != "Orphan"
    assert "TRIP" not in mapped[0] or mapped[0].get("TRIP") != "Orphan"


def test_column_mapping_drift_handling():
    """Test that column drift is handled correctly."""
    headers = {
        "CKT": 100.0,
        "LOAD_NAME": 200.0,
    }
    
    # Words that drift slightly but stay within tolerance
    words = [
        (102.0, 50.0, 108.0, 60.0, "1", 0, 0, 0),  # Slight drift in CKT column
        (198.0, 50.0, 202.0, 60.0, "Load1", 0, 0, 0),  # Slight drift in LOAD_NAME
        (104.0, 70.0, 106.0, 80.0, "2", 0, 0, 0),  # More drift, still within tolerance
        (201.0, 70.0, 199.0, 80.0, "Load2", 0, 0, 0),  # Drift the other way
    ]
    
    mapped = map_values_to_columns(words, headers, tolerance=30.0)
    
    assert len(mapped) == 2
    # Both should still map to correct columns despite drift
    assert mapped[0]["CKT"] == "1"
    assert mapped[0]["LOAD_NAME"] == "Load1"
    assert mapped[1]["CKT"] == "2"
    assert mapped[1]["LOAD_NAME"] == "Load2"


def test_column_mapping_empty_headers():
    """Test that empty headers return empty mapping."""
    words = [
        (100.0, 50.0, 110.0, 60.0, "Test", 0, 0, 0),
    ]
    
    mapped = map_values_to_columns(words, {}, tolerance=30.0)
    
    assert mapped == {}


def test_column_mapping_multiple_words_per_column():
    """Test that multiple words in the same column are concatenated."""
    headers = {
        "LOAD_NAME": 200.0,
    }
    
    # Multiple words that should map to the same column
    words = [
        (198.0, 50.0, 202.0, 60.0, "Main", 0, 0, 0),
        (202.0, 50.0, 206.0, 60.0, "Panel", 0, 0, 0),  # Same row, same column
    ]
    
    mapped = map_values_to_columns(words, headers, tolerance=30.0)
    
    assert len(mapped) == 1
    assert mapped[0]["LOAD_NAME"] == "Main Panel"

