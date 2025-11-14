"""Unit tests for individual transform modules."""
from __future__ import annotations

import pytest

from tools.schedule_postpass.ids import leftpad_circuit, make_document_id, sanitize_key_component, stable_key
from tools.schedule_postpass.metadata import _to_iso_date, sheet_meta


def test_sanitize_key_component() -> None:
    """Test key component sanitization."""
    assert sanitize_key_component("normal-text") == "normal-text"
    assert sanitize_key_component("text with spaces") == "text-with-spaces"
    assert sanitize_key_component("text@with#special$chars") == "text-with-special-chars"
    assert sanitize_key_component("") == "none"
    assert sanitize_key_component(None) == "none"
    assert sanitize_key_component("---") == "none"
    assert sanitize_key_component("  multiple---dashes  ") == "multiple-dashes"
    assert sanitize_key_component("UPPERCASE") == "UPPERCASE"
    assert sanitize_key_component("MixedCase123") == "MixedCase123"


def test_make_document_id() -> None:
    """Test document ID generation."""
    assert make_document_id("project", "sheet", "rev") == "project-sheet-rev"
    assert make_document_id("project", "", "rev") == "project-none-rev"
    assert make_document_id() == "doc"
    assert make_document_id("project@name", "sheet#1", "rev-2") == "project-name-sheet-1-rev-2"
    assert make_document_id("  ", None, "valid") == "none-none-valid"


def test_leftpad_circuit() -> None:
    """Test circuit number left-padding."""
    assert leftpad_circuit(5) == "005"
    assert leftpad_circuit("5") == "005"
    assert leftpad_circuit(123) == "123"
    assert leftpad_circuit("123") == "123"
    assert leftpad_circuit("abc") == "abc"
    assert leftpad_circuit("") == ""
    assert leftpad_circuit(None) == "None"


def test_stable_key() -> None:
    """Test stable key generation."""
    assert stable_key("panel", {"panel": "S2", "circuit": "5"}) == "panel-circuit-005-panel-S2"
    assert stable_key("unit_plan", {"unit": "A4", "tag": "DW"}) == "unit_plan-tag-DW-unit-A4"
    assert stable_key("lighting_fixture", {"tag": "LED"}) == "lighting_fixture-tag-LED"
    assert stable_key("panel", {"panel": "S2", "circuit": 123}) == "panel-circuit-123-panel-S2"


def test_to_iso_date() -> None:
    """Test ISO date conversion."""
    assert _to_iso_date("2025-04-18") == "2025-04-18T00:00:00Z"
    assert _to_iso_date("04/18/2025") == "2025-04-18T00:00:00Z"
    assert _to_iso_date("04/18/25") == "2025-04-18T00:00:00Z"
    assert _to_iso_date("2025-04-18T10:30:00Z") == "2025-04-18T10:30:00Z"
    assert _to_iso_date("") == "2000-01-01T00:00:00Z"
    assert _to_iso_date(None) == "2000-01-01T00:00:00Z"
    assert _to_iso_date(1713456000) == "2024-04-19T00:00:00Z"  # Unix timestamp
    assert _to_iso_date(1713456000.0) == "2024-04-19T00:00:00Z"  # Float timestamp


def test_sheet_meta_discipline_explicit() -> None:
    """Test that explicit discipline field is honored."""
    raw = {
        "sheet_number": "E5.00",
        "discipline": "electrical",
        "DRAWING_METADATA": {"sheet_number": "E5.00"},
    }
    meta = sheet_meta(raw, "test-project")
    assert meta["discipline"] == "electrical"


def test_sheet_meta_discipline_inferred_from_electrical() -> None:
    """Test that discipline is inferred from ELECTRICAL section when missing."""
    raw = {
        "sheet_number": "E5.00",
        "DRAWING_METADATA": {"sheet_number": "E5.00"},
        "ELECTRICAL": {
            "panels": [{"panel_name": "LP-1", "circuits": []}],
        },
    }
    meta = sheet_meta(raw, "test-project")
    assert meta["discipline"] == "electrical"


def test_sheet_meta_discipline_inferred_from_mechanical() -> None:
    """Test that discipline is inferred from MECHANICAL section."""
    raw = {
        "sheet_number": "M1.00",
        "MECHANICAL": {
            "equipment": [{"tag": "AHU-1"}],
        },
    }
    meta = sheet_meta(raw, "test-project")
    assert meta["discipline"] == "mechanical"


def test_sheet_meta_discipline_inferred_from_plumbing() -> None:
    """Test that discipline is inferred from PLUMBING section."""
    raw = {
        "sheet_number": "P1.00",
        "PLUMBING": {
            "fixtures": [{"fixture_id": "WC-1"}],
        },
    }
    meta = sheet_meta(raw, "test-project")
    assert meta["discipline"] == "plumbing"


def test_sheet_meta_discipline_inferred_from_architectural() -> None:
    """Test that discipline is inferred from ARCHITECTURAL section."""
    raw = {
        "sheet_number": "A1.00",
        "ARCHITECTURAL": {
            "DOOR_SCHEDULE": [{"door_number": "101"}],
        },
    }
    meta = sheet_meta(raw, "test-project")
    assert meta["discipline"] == "architectural"


def test_sheet_meta_discipline_fallback_when_no_sections() -> None:
    """Test that discipline falls back to architectural when no sections exist."""
    raw = {
        "sheet_number": "X1.00",
    }
    meta = sheet_meta(raw, "test-project")
    assert meta["discipline"] == "architectural"


def test_sheet_meta_discipline_fallback_when_multiple_sections() -> None:
    """Test that discipline falls back to architectural when multiple sections exist."""
    raw = {
        "sheet_number": "E5.00",
        "ELECTRICAL": {"panels": []},
        "MECHANICAL": {"equipment": []},
    }
    meta = sheet_meta(raw, "test-project")
    assert meta["discipline"] == "architectural"


def test_sheet_meta_discipline_explicit_overrides_inference() -> None:
    """Test that explicit discipline overrides inference from sections."""
    raw = {
        "sheet_number": "E5.00",
        "discipline": "mechanical",
        "ELECTRICAL": {
            "panels": [{"panel_name": "LP-1"}],
        },
    }
    meta = sheet_meta(raw, "test-project")
    assert meta["discipline"] == "mechanical"

