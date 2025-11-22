import fitz

from utils.minimal_panel_clip import (
    compute_left_right_split,
    _extend_panel_bottom_with_content,
    build_panel_row_hints,
)


class StubPage:
    def __init__(self, words, rect=None):
        self._words = words
        self.rect = rect or fitz.Rect(0, 0, 612, 792)

    def get_text(self, mode, clip=None, sort=False):
        assert mode == "words"
        return self._words


def test_compute_left_right_split_headers_two_clusters():
    rect = fitz.Rect(0, 0, 600, 800)
    words = [
        (20.0, 10.0, 40.0, 30.0, "CKT", 0, 0, 0),
        (500.0, 12.0, 520.0, 32.0, "CKT", 0, 0, 0),
    ]
    page = StubPage(words)

    left_rect, right_rect, split_x = compute_left_right_split(
        page, rect, header_band_px=200.0, max_header_band_px=400.0, near_center_bias=0.2
    )

    assert 200.0 < split_x < 400.0
    assert left_rect.x1 == split_x
    assert right_rect.x0 == split_x


def test_compute_left_right_split_fallback_midpoint():
    rect = fitz.Rect(0, 0, 600, 800)
    words = [
        (50.0, 15.0, 70.0, 35.0, "LOAD NAME", 0, 0, 0),
    ]
    page = StubPage(words)

    left_rect, right_rect, split_x = compute_left_right_split(
        page, rect, header_band_px=150.0, max_header_band_px=200.0, near_center_bias=0.3
    )

    assert split_x > rect.x0 + 50.0
    assert right_rect.x0 == split_x


def test_extend_panel_bottom_with_content():
    words = [
        (10.0, 40.0, 30.0, 50.0, "CKT", 0, 0, 0),
        (12.0, 300.0, 32.0, 320.0, "15", 0, 0, 0),
    ]
    extended_bottom = _extend_panel_bottom_with_content(
        words,
        x_left=0.0,
        x_right=60.0,
        y_top=20.0,
        default_bottom=120.0,
        pad=10.0,
        page_bottom=800.0,
    )

    assert extended_bottom > 120.0
    assert extended_bottom <= 330.0


def test_build_panel_row_hints_groups_by_panel():
    """Test that panel row hints correctly group circuits by panel."""
    rect = fitz.Rect(0, 0, 400, 400)
    words = [
        (10.0, 10.0, 40.0, 25.0, "Panel", 0, 0, 0),
        (45.0, 10.0, 65.0, 25.0, "K1", 0, 0, 1),
        (10.0, 60.0, 20.0, 72.0, "1", 0, 1, 0),
        (25.0, 60.0, 90.0, 72.0, "LIGHTING", 0, 1, 1),
        (95.0, 60.0, 120.0, 72.0, "20", 0, 1, 2),
        (130.0, 60.0, 165.0, 72.0, "A", 0, 1, 3),
        (10.0, 95.0, 20.0, 107.0, "2", 0, 2, 0),
        (25.0, 95.0, 80.0, 107.0, "SPARE", 0, 2, 1),
        (85.0, 95.0, 110.0, 107.0, "20", 0, 2, 2),
        (120.0, 95.0, 145.0, 107.0, "A", 0, 2, 3),
        (10.0, 200.0, 40.0, 215.0, "Panel", 0, 3, 0),
        (45.0, 200.0, 75.0, 215.0, "L1", 0, 3, 1),
        (10.0, 240.0, 20.0, 252.0, "1", 0, 4, 0),
        (25.0, 240.0, 80.0, 252.0, "COFFEE", 0, 4, 1),
        (85.0, 240.0, 110.0, 252.0, "15", 0, 4, 2),
        (120.0, 240.0, 145.0, 252.0, "A", 0, 4, 3),
    ]
    page = StubPage(words, rect=rect)
    panels = build_panel_row_hints(page, words)

    assert len(panels) == 2
    assert panels[0]["panel_id"] == "K1"
    assert len(panels[0]["rows"]) == 2
    assert panels[0]["rows"][0]["ckt"] == 1
    assert panels[0]["rows"][1]["ckt"] == 2
    assert panels[1]["panel_id"] == "L1"
    assert len(panels[1]["rows"]) == 1
    assert panels[1]["rows"][0]["ckt"] == 1

