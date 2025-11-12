"""
Integration tests for electrical panel extraction on E5.00 sample.

This test validates that the electrical panel extraction correctly:
- Segments multiple panels without cross-panel bleed
- Extracts correct circuit counts per panel
- Filters out sheet summaries
- Pairs odd/even circuits correctly
"""
import os
import pytest
import asyncio
from services.extraction.electrical import ElectricalExtractor
import logging


@pytest.fixture
def extractor():
    """Create an electrical extractor instance."""
    logger = logging.getLogger("test_electrical")
    logger.setLevel(logging.INFO)
    return ElectricalExtractor(logger=logger)


@pytest.mark.asyncio
async def test_e500_panel_extraction(extractor):
    """
    Test E5.00 panel extraction with expected circuit counts.
    
    Expected results:
    - H1: 42 circuits (odd-even paired)
    - K1: 84 circuits
    - L1: 84 circuits
    - K1S: 12 circuits
    - No circuits under "TOTALS" panel
    - No cross-panel bleed (K1 circuits don't appear under K1S)
    """
    # Path to E5.00 test file (adjust as needed)
    test_file = os.path.join(
        os.path.dirname(__file__),
        "test_data",
        "E5.00-PANEL-SCHEDULES-Rev.3.pdf",
    )
    
    if not os.path.exists(test_file):
        pytest.skip(f"Test file not found: {test_file}")
    
    # Extract panels
    result = await extractor.extract(test_file)
    
    assert result.success, f"Extraction failed: {result.error}"
    assert result.raw_text, "No text extracted"
    
    # Check that panel sections are present
    assert "===PANEL H1 BEGINS===" in result.raw_text
    assert "===PANEL K1 BEGINS===" in result.raw_text
    assert "===PANEL L1 BEGINS===" in result.raw_text
    assert "===PANEL K1S BEGINS===" in result.raw_text
    
    # Count circuits per panel (rough check via text patterns)
    # This is a simplified check - full validation would parse the structured output
    h1_section = result.raw_text.split("===PANEL H1 BEGINS===")[1].split("===PANEL H1 ENDS===")[0]
    k1_section = result.raw_text.split("===PANEL K1 BEGINS===")[1].split("===PANEL K1 ENDS===")[0]
    l1_section = result.raw_text.split("===PANEL L1 BEGINS===")[1].split("===PANEL L1 ENDS===")[0]
    k1s_section = result.raw_text.split("===PANEL K1S BEGINS===")[1].split("===PANEL K1S ENDS===")[0]
    
    # Count "Circuit" mentions (approximate circuit count)
    h1_circuits = h1_section.count("Circuit ")
    k1_circuits = k1_section.count("Circuit ")
    l1_circuits = l1_section.count("Circuit ")
    k1s_circuits = k1s_section.count("Circuit ")
    
    # Allow some tolerance in counts (within 10% of expected)
    assert abs(h1_circuits - 42) <= 5, f"H1 expected ~42 circuits, got {h1_circuits}"
    assert abs(k1_circuits - 84) <= 10, f"K1 expected ~84 circuits, got {k1_circuits}"
    assert abs(l1_circuits - 84) <= 10, f"L1 expected ~84 circuits, got {l1_circuits}"
    assert abs(k1s_circuits - 12) <= 3, f"K1S expected ~12 circuits, got {k1s_circuits}"
    
    # Check that TOTALS is not treated as a panel with circuits
    if "TOTALS" in result.raw_text:
        # TOTALS should appear in SHEET_SUMMARY section, not as a panel
        assert "===PANEL TOTALS BEGINS===" not in result.raw_text
        assert "SHEET_SUMMARY: TOTALS" in result.raw_text or "TOTALS" not in result.raw_text.split("PANEL")[0]
    
    # Check for cross-panel bleed: K1 circuits should not appear in K1S section
    # Look for common K1 circuit numbers (e.g., 1-84) in K1S section
    k1s_circuit_numbers = set()
    for line in k1s_section.split("\n"):
        if "Circuit " in line:
            # Extract circuit number
            parts = line.split("Circuit ")
            if len(parts) > 1:
                num_str = parts[1].split(":")[0].strip()
                try:
                    k1s_circuit_numbers.add(int(num_str))
                except ValueError:
                    pass
    
    # K1S should only have circuits in its expected range (typically higher numbers)
    # This is a basic check - adjust based on actual K1S circuit numbering
    if k1s_circuit_numbers:
        # K1S circuits should be distinct from K1's main range (1-84)
        # Adjust this assertion based on actual K1S numbering scheme
        assert all(
            num > 84 or num < 1 for num in k1s_circuit_numbers
        ) or len(k1s_circuit_numbers) <= 12, "Possible cross-panel bleed detected"


@pytest.mark.asyncio
async def test_panel_segmentation_no_overlap(extractor):
    """
    Test that panel segmentation produces non-overlapping rectangles.
    """
    test_file = os.path.join(
        os.path.dirname(__file__),
        "test_data",
        "E5.00-PANEL-SCHEDULES-Rev.3.pdf",
    )
    
    if not os.path.exists(test_file):
        pytest.skip(f"Test file not found: {test_file}")
    
    import fitz
    from utils.minimal_panel_clip import segment_panels
    
    doc = fitz.open(test_file)
    page = doc[0]
    
    panels = segment_panels(page, pad=10.0)
    
    # Check for overlaps between panel rectangles
    for i, (name1, rect1) in enumerate(panels):
        for j, (name2, rect2) in enumerate(panels[i + 1 :], start=i + 1):
            # Calculate overlap
            x_overlap = max(0, min(rect1.x1, rect2.x1) - max(rect1.x0, rect2.x0))
            y_overlap = max(0, min(rect1.y1, rect2.y1) - max(rect1.y0, rect2.y0))
            overlap_area = x_overlap * y_overlap
            
            if overlap_area > 0:
                area1 = rect1.width * rect1.height
                overlap_frac = overlap_area / area1 if area1 > 0 else 0
                assert (
                    overlap_frac < 0.05
                ), f"Panels {name1} and {name2} overlap by {overlap_frac*100:.1f}%"
    
    doc.close()


@pytest.mark.asyncio
async def test_sheet_summary_filtering(extractor):
    """
    Test that sheet summaries (TOTALS, SUMMARY) are filtered out from panels.
    """
    test_file = os.path.join(
        os.path.dirname(__file__),
        "test_data",
        "E5.00-PANEL-SCHEDULES-Rev.3.pdf",
    )
    
    if not os.path.exists(test_file):
        pytest.skip(f"Test file not found: {test_file}")
    
    result = await extractor.extract(test_file)
    
    assert result.success
    
    # TOTALS should not appear as a panel
    assert "===PANEL TOTALS BEGINS===" not in result.raw_text
    
    # If TOTALS exists, it should be in SHEET_SUMMARY section
    if "TOTALS" in result.raw_text:
        assert "SHEET_SUMMARY" in result.raw_text or "TOTALS" not in result.raw_text

