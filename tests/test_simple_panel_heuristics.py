"""
Unit tests for simple_panel_heuristics module.

Tests lightweight text-based heuristics for panel schedule detection and classification.
"""
import pytest
from services.extraction.electrical.simple_panel_heuristics import (
    split_into_panels,
    classify_line,
    is_circuit_row,
    is_summary_line,
    detect_circuits_per_line,
    find_header_row,
    extract_panel_metadata,
    annotate_text_with_panel_markers,
    score_table_for_panel,
    process_panel_text,
)


def test_split_into_panels():
    """Test panel segmentation from text lines."""
    lines = [
        "Some header text",
        "Panel: K1",
        "Circuit Load Name Trip",
        "1 Kitchen 20 A",
        "2 Space --",
        "Panel: L1",
        "Circuit Load Name Trip",
        "1 Receptacle 15 A",
        "Panel: H1",
        "Circuit Load Name Trip",
        "1 Lighting 20 A",
    ]
    
    panels = split_into_panels(lines)
    
    assert len(panels) == 3
    assert panels[0]["panel_id"] == "K1"
    assert panels[0]["start"] == 1
    assert panels[1]["panel_id"] == "L1"
    assert panels[2]["panel_id"] == "H1"


def test_split_into_panels_no_panels():
    """Test panel segmentation with no panels."""
    lines = [
        "Some text",
        "No panels here",
        "Just regular content",
    ]
    
    panels = split_into_panels(lines)
    assert len(panels) == 0


def test_classify_line_circuit():
    """Test circuit row classification."""
    circuit_lines = [
        "Kitchen Equipment 83 Slushie Machine* 20 A 1 1411 VA 2089 VA",
        "Receptacle 15 A 120 VA",
        "Lighting 20 A 240 VA",
    ]
    
    for line in circuit_lines:
        assert classify_line(line) == "circuit"


def test_classify_line_summary():
    """Test summary line classification."""
    summary_lines = [
        "Total Connected Load: 82353 VA",
        "Panel Totals: 64990 VA 65.00%",
        "Connected Load: 5000 VA",
    ]
    
    for line in summary_lines:
        assert classify_line(line) == "summary"


def test_classify_line_other():
    """Test other line classification."""
    other_lines = [
        "Panel: K1",
        "Circuit Load Name Trip",
        "Some random text",
    ]
    
    for line in other_lines:
        assert classify_line(line) == "other"


def test_is_circuit_row():
    """Test circuit row detection."""
    assert is_circuit_row("Kitchen 83 Slushie Machine* 20 A 1 1411 VA")
    assert is_circuit_row("Receptacle 15 A 120 VA")
    assert is_circuit_row("Lighting 20 A")
    assert not is_circuit_row("Total Connected Load: 82353 VA")
    assert not is_circuit_row("Panel: K1")
    assert not is_circuit_row("Circuit Load Name Trip")


def test_is_summary_line():
    """Test summary line detection."""
    assert is_summary_line("Total Connected Load: 82353 VA")
    assert is_summary_line("Panel Totals: 64990 VA 65.00%")
    assert is_summary_line("Connected Load: 5000 VA")
    assert not is_summary_line("Kitchen 83 Slushie Machine* 20 A 1 1411 VA")
    assert not is_summary_line("Panel: K1")


def test_detect_circuits_per_line_one():
    """Test detection of 1 circuit per line."""
    lines = [
        "Panel: K1",
        "Circuit Load Name Trip",
        "1 Kitchen 20 A 120 VA",
        "2 Receptacle 15 A 180 VA",
        "3 Lighting 20 A 240 VA",
    ]
    
    result = detect_circuits_per_line(lines)
    assert result == 1


def test_detect_circuits_per_line_two():
    """Test detection of 2 circuits per line."""
    lines = [
        "Panel: K1",
        "Circuit Load Name Trip",
        "Kitchen... 83 Slushie Machine* 20 A 1 1411 VA 84 Space 15 A 1 120 VA",
        "Receptacle 85 Outlet 15 A 1 120 VA 86 Lighting 20 A 1 240 VA",
    ]
    
    result = detect_circuits_per_line(lines)
    assert result == 2


def test_find_header_row():
    """Test header row detection."""
    lines = [
        "Panel: K1",
        "Rating: 400 A",
        "Load Classification CKT Load Name Trip Poles A B C",
        "1 Kitchen 20 A 1 120 VA",
    ]
    
    idx = find_header_row(lines)
    assert idx == 2


def test_find_header_row_not_found():
    """Test header row detection when not present."""
    lines = [
        "Panel: K1",
        "Some text",
        "No header here",
    ]
    
    idx = find_header_row(lines)
    assert idx is None


def test_extract_panel_metadata():
    """Test panel metadata extraction."""
    lines = [
        "Panel: K1",
        "Rating: 400 A",
        "Volts: 120/208 Wye",
        "Type: MCB",
        "Supply From: TL1",
        "A.I.C. Rating: 14K",
        "Circuit Load Name Trip",
    ]
    
    metadata = extract_panel_metadata(lines)
    
    assert metadata["rating_amps"] == 400
    assert "120/208" in metadata["voltage"]
    assert metadata["type"] == "MCB"
    assert metadata["supply_from"] == "TL1"
    assert metadata["aic_rating"] == "14K"


def test_annotate_text_with_panel_markers():
    """Test text annotation with panel markers."""
    raw_text = "Header\nPanel: K1\nLine 1\nLine 2\nPanel: L1\nLine 3"
    lines = raw_text.split("\n")
    panels = split_into_panels(lines)
    
    annotated = annotate_text_with_panel_markers(raw_text, panels)
    
    assert "=== PANEL SCHEDULE: K1 ===" in annotated
    assert "=== END PANEL SCHEDULE: K1 ===" in annotated
    assert "=== PANEL SCHEDULE: L1 ===" in annotated
    assert "=== END PANEL SCHEDULE: L1 ===" in annotated


def test_score_table_for_panel():
    """Test table scoring for panel relevance."""
    panel_table = {
        "data": "Panel K1 Circuit 1 Kitchen 20 A",
        "headers": ["Circuit", "Load", "Trip"],
    }
    
    other_table = {
        "data": "Some other data",
        "headers": ["Column1", "Column2"],
    }
    
    score_panel = score_table_for_panel(panel_table, "K1")
    score_other = score_table_for_panel(other_table, "K1")
    
    assert score_panel > score_other
    assert score_panel >= 10.0


def test_process_panel_text():
    """Test main processing function."""
    raw_text = """Header text
Panel: K1
Rating: 400 A
Circuit Load Name Trip
1 Kitchen 20 A 120 VA
2 Space --
Total: 120 VA
Panel: L1
Circuit Load Name Trip
1 Receptacle 15 A 180 VA
"""
    
    result = process_panel_text(raw_text)
    
    assert result["panel_count"] == 2
    assert len(result["panels"]) == 2
    assert result["panels"][0]["panel_id"] == "K1"
    assert result["panels"][1]["panel_id"] == "L1"
    assert "=== PANEL SCHEDULE: K1 ===" in result["annotated_text"]
    assert "=== PANEL SCHEDULE: L1 ===" in result["annotated_text"]


def test_process_panel_text_no_panels():
    """Test processing with no panels."""
    raw_text = "Just some regular text\nNo panels here"
    
    result = process_panel_text(raw_text)
    
    assert result["panel_count"] == 0
    assert len(result["panels"]) == 0
    assert result["annotated_text"] == raw_text


def test_process_panel_text_empty():
    """Test processing with empty text."""
    result = process_panel_text("")
    
    assert result["panel_count"] == 0
    assert len(result["panels"]) == 0
    assert result["annotated_text"] == ""

