"""Unit tests for page number inference utilities."""
from __future__ import annotations

import pytest

try:
    from tools.schedule_postpass.page_utils import infer_page
except ImportError:
    import sys
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root))
    from tools.schedule_postpass.page_utils import infer_page  # type: ignore


def test_infer_page_from_page_number() -> None:
    """Test infer_page reads page_number field."""
    raw = {"page_number": 5, "sheet_number": "E2.03"}
    assert infer_page(raw) == 5


def test_infer_page_from_page() -> None:
    """Test infer_page reads page field as fallback."""
    raw = {"page": 3, "sheet_number": "E2.03"}
    assert infer_page(raw) == 3


def test_infer_page_from_sheet_index() -> None:
    """Test infer_page reads sheet_index field as fallback."""
    raw = {"sheet_index": 7, "sheet_number": "E2.03"}
    assert infer_page(raw) == 7


def test_infer_page_from_drawing_metadata() -> None:
    """Test infer_page reads page_number from DRAWING_METADATA."""
    raw = {
        "sheet_number": "E2.03",
        "DRAWING_METADATA": {"page_number": 4}
    }
    assert infer_page(raw) == 4


def test_infer_page_prefers_top_level() -> None:
    """Test infer_page prefers top-level page_number over metadata."""
    raw = {
        "page_number": 2,
        "DRAWING_METADATA": {"page_number": 9}
    }
    assert infer_page(raw) == 2


def test_infer_page_string_conversion() -> None:
    """Test infer_page converts string values to integers."""
    raw = {"page_number": "6"}
    assert infer_page(raw) == 6


def test_infer_page_defaults_to_one() -> None:
    """Test infer_page defaults to 1 when no page info found."""
    raw = {"sheet_number": "E2.03", "content": "some content"}
    assert infer_page(raw) == 1


def test_infer_page_ignores_invalid_values() -> None:
    """Test infer_page ignores negative or zero values."""
    raw = {"page_number": -1, "page": 0}
    assert infer_page(raw) == 1


def test_infer_page_handles_missing_keys() -> None:
    """Test infer_page handles empty dict gracefully."""
    raw = {}
    assert infer_page(raw) == 1

