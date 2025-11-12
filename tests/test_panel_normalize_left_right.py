"""
Unit tests for normalize_left_right function.
"""
import pytest
from utils.minimal_panel_clip import normalize_left_right


def test_normalize_swaps_odd_even():
    """Test that odd/even swaps are corrected."""
    rows = [
        {
            "circuit_number": 2,  # Even on left (wrong)
            "load_name": "Load2",
            "trip": "20 A",
            "poles": 1,
            "phase_loads": {"A": "100", "B": None, "C": None},
            "right_side": {
                "circuit_number": 1,  # Odd on right (wrong)
                "load_name": "Load1",
                "trip": "15 A",
                "poles": 1,
                "phase_loads": {"A": "50", "B": None, "C": None},
            },
        },
    ]
    
    normalized = normalize_left_right(rows)
    
    assert len(normalized) == 1
    # Should be swapped: odd on left, even on right
    assert normalized[0]["circuit_number"] == 1
    assert normalized[0]["load_name"] == "Load1"
    assert normalized[0]["right_side"]["circuit_number"] == 2
    assert normalized[0]["right_side"]["load_name"] == "Load2"


def test_normalize_handles_missing_right_side():
    """Test that missing right side is handled correctly."""
    rows = [
        {
            "circuit_number": 1,  # Odd on left (correct)
            "load_name": "Load1",
            "trip": "20 A",
            "poles": 1,
            "phase_loads": {"A": "100", "B": None, "C": None},
            "right_side": {},  # Empty right side
        },
    ]
    
    normalized = normalize_left_right(rows)
    
    assert len(normalized) == 1
    assert normalized[0]["circuit_number"] == 1
    assert normalized[0]["right_side"] == {}


def test_normalize_moves_even_to_right():
    """Test that even circuit numbers are moved to right side if no right exists."""
    rows = [
        {
            "circuit_number": 2,  # Even on left, no right side
            "load_name": "Load2",
            "trip": "20 A",
            "poles": 1,
            "phase_loads": {"A": "100", "B": None, "C": None},
            "right_side": {},
        },
    ]
    
    normalized = normalize_left_right(rows)
    
    assert len(normalized) == 1
    # Even should be moved to right, left cleared
    assert normalized[0]["circuit_number"] is None
    assert normalized[0]["right_side"]["circuit_number"] == 2
    assert normalized[0]["right_side"]["load_name"] == "Load2"


def test_normalize_preserves_correct_ordering():
    """Test that correctly ordered circuits are preserved."""
    rows = [
        {
            "circuit_number": 1,  # Odd on left (correct)
            "load_name": "Load1",
            "trip": "20 A",
            "poles": 1,
            "phase_loads": {"A": "100", "B": None, "C": None},
            "right_side": {
                "circuit_number": 2,  # Even on right (correct)
                "load_name": "Load2",
                "trip": "15 A",
                "poles": 1,
                "phase_loads": {"A": "50", "B": None, "C": None},
            },
        },
        {
            "circuit_number": 3,  # Odd on left (correct)
            "load_name": "Load3",
            "trip": "30 A",
            "poles": 2,
            "phase_loads": {"A": "200", "B": "200", "C": None},
            "right_side": {
                "circuit_number": 4,  # Even on right (correct)
                "load_name": "Load4",
                "trip": "25 A",
                "poles": 1,
                "phase_loads": {"A": "75", "B": None, "C": None},
            },
        },
    ]
    
    normalized = normalize_left_right(rows)
    
    assert len(normalized) == 2
    # Should be unchanged
    assert normalized[0]["circuit_number"] == 1
    assert normalized[0]["right_side"]["circuit_number"] == 2
    assert normalized[1]["circuit_number"] == 3
    assert normalized[1]["right_side"]["circuit_number"] == 4


def test_normalize_handles_none_circuit_numbers():
    """Test that None circuit numbers are handled gracefully."""
    rows = [
        {
            "circuit_number": None,
            "load_name": "Load1",
            "trip": "20 A",
            "poles": 1,
            "phase_loads": {"A": "100", "B": None, "C": None},
            "right_side": {
                "circuit_number": 2,
                "load_name": "Load2",
                "trip": "15 A",
                "poles": 1,
                "phase_loads": {"A": "50", "B": None, "C": None},
            },
        },
    ]
    
    normalized = normalize_left_right(rows)
    
    assert len(normalized) == 1
    # Should handle None gracefully
    assert normalized[0]["circuit_number"] is None
    assert normalized[0]["right_side"]["circuit_number"] == 2

