import fitz

from utils.minimal_panel_clip import (
    compute_left_right_split,
    _extend_panel_bottom_with_content,
)


class StubPage:
    def __init__(self, words):
        self._words = words

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

