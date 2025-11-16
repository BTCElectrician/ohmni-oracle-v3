"""
Tests for panel text post-pass functionality.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from tools.schedule_postpass.panel_text_postpass import (
    fill_panels_from_sheet_text,
    is_panel_schedule_sheet,
    _update_panel_circuits,
    _count_existing_circuits,
)


def test_is_panel_schedule_sheet_with_panels_list():
    """Test detection of panel schedule with panels list."""
    sheet_json = {
        "ELECTRICAL": {
            "panels": [
                {"panel_name": "K1", "circuits": []}
            ]
        }
    }
    assert is_panel_schedule_sheet(sheet_json) is True


def test_is_panel_schedule_sheet_with_panel_schedules_dict():
    """Test detection of panel schedule with PANEL_SCHEDULES dict."""
    sheet_json = {
        "ELECTRICAL": {
            "PANEL_SCHEDULES": {
                "K1": {"circuit_details": []}
            }
        }
    }
    assert is_panel_schedule_sheet(sheet_json) is True


def test_is_panel_schedule_sheet_with_title():
    """Test detection via drawing title."""
    sheet_json = {
        "DRAWING_METADATA": {
            "title": "PANEL SCHEDULES"
        },
        "ELECTRICAL": {}
    }
    assert is_panel_schedule_sheet(sheet_json) is True


def test_is_panel_schedule_sheet_not_panel():
    """Test that non-panel sheets return False."""
    sheet_json = {
        "ELECTRICAL": {
            "equipment": []
        }
    }
    assert is_panel_schedule_sheet(sheet_json) is False


@pytest.mark.asyncio
async def test_fill_panels_from_sheet_text_updates_circuits():
    """Test that fill_panels_from_sheet_text updates panel circuits."""
    # Mock OpenAI client
    mock_client = AsyncMock()
    
    # Mock response for K1 panel
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """{
  "panel_name": "K1",
  "circuits": [
    {
      "circuit_number": 1,
      "load_name": "TEST LOAD 1",
      "trip_amps": 20,
      "is_spare_or_space": false
    },
    {
      "circuit_number": 2,
      "load_name": "TEST LOAD 2",
      "trip_amps": 20,
      "is_spare_or_space": false
    },
    {
      "circuit_number": 3,
      "load_name": "SPACE",
      "trip_amps": null,
      "is_spare_or_space": true
    }
  ]
}"""
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50
    mock_response.usage.total_tokens = 150
    
    # Mock the chat completions create method
    async def mock_create(**kwargs):
        return mock_response
    
    mock_client.chat.completions.create = mock_create
    
    # Test data
    sheet_json = {
        "ELECTRICAL": {
            "panels": [
                {
                    "panel_name": "K1",
                    "circuits": [
                        {"circuit_number": 1, "load_name": "EXISTING LOAD"}
                    ]
                }
            ]
        }
    }
    
    sheet_text = """Panel: K1
Circuit 1: TEST LOAD 1
Circuit 2: TEST LOAD 2
Circuit 3: SPACE"""
    
    result = await fill_panels_from_sheet_text(
        sheet_json=sheet_json,
        sheet_text=sheet_text,
        client=mock_client,
    )
    
    # Verify K1 panel was updated
    k1_panel = next(
        (p for p in result["ELECTRICAL"]["panels"] if p.get("panel_name") == "K1"),
        None
    )
    assert k1_panel is not None
    assert len(k1_panel["circuits"]) == 3
    
    # Verify even circuit (2) is present
    circuit_2 = next(
        (c for c in k1_panel["circuits"] if c.get("circuit_number") == 2),
        None
    )
    assert circuit_2 is not None
    assert circuit_2["load_name"] == "TEST LOAD 2"
    
    # Verify circuit 3 (spare/space) is present
    circuit_3 = next(
        (c for c in k1_panel["circuits"] if c.get("circuit_number") == 3),
        None
    )
    assert circuit_3 is not None


@pytest.mark.asyncio
async def test_fill_panels_from_sheet_text_handles_errors_gracefully():
    """Test that errors in model calls don't crash the pipeline."""
    # Mock client that raises an exception
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))
    
    sheet_json = {
        "ELECTRICAL": {
            "panels": [
                {"panel_name": "K1", "circuits": []}
            ]
        }
    }
    
    sheet_text = "Panel: K1\nSome text"
    
    # Should not raise, should return original data
    result = await fill_panels_from_sheet_text(
        sheet_json=sheet_json,
        sheet_text=sheet_text,
        client=mock_client,
    )
    
    # Should return original structure (may be modified but shouldn't crash)
    assert "ELECTRICAL" in result
    assert len(result["ELECTRICAL"]["panels"]) == 1


def test_count_existing_circuits():
    """Test counting existing circuits."""
    electrical = {
        "panels": [
            {
                "panel_name": "K1",
                "circuits": [
                    {"circuit_number": 1},
                    {"circuit_number": 3},
                    {"circuit_number": 5},
                ]
            }
        ]
    }
    
    count = _count_existing_circuits(electrical, "K1")
    assert count == 3


def test_update_panel_circuits_in_panels_list():
    """Test updating circuits in panels list."""
    electrical = {
        "panels": [
            {
                "panel_name": "K1",
                "circuits": [{"circuit_number": 1}],
                "enclosure_info": {"volts": "120/208"}
            }
        ]
    }
    
    new_circuits = [
        {"circuit_number": 1, "load_name": "LOAD 1"},
        {"circuit_number": 2, "load_name": "LOAD 2"},
    ]
    
    _update_panel_circuits(electrical, "K1", new_circuits)
    
    k1 = next(p for p in electrical["panels"] if p["panel_name"] == "K1")
    assert len(k1["circuits"]) == 2
    assert k1["enclosure_info"]["volts"] == "120/208"  # Metadata preserved


def test_update_panel_circuits_in_panel_schedules_dict():
    """Test updating circuits in PANEL_SCHEDULES dict."""
    electrical = {
        "PANEL_SCHEDULES": {
            "K1": {
                "circuit_details": [{"circuit_number": 1}],
                "voltage": "120/208"
            }
        }
    }
    
    new_circuits = [
        {"circuit_number": 1, "load_name": "LOAD 1"},
        {"circuit_number": 2, "load_name": "LOAD 2"},
    ]
    
    _update_panel_circuits(electrical, "K1", new_circuits)
    
    k1 = electrical["PANEL_SCHEDULES"]["K1"]
    assert len(k1["circuit_details"]) == 2
    assert k1["voltage"] == "120/208"  # Metadata preserved

