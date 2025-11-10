"""
Tests for pipeline template generation step.

Tests floor plan detection (filename and metadata-based) and flattened output layout.
"""
import json
import os
from pathlib import Path
from unittest import mock
from unittest.mock import AsyncMock, MagicMock

import pytest

from processing.pipeline.templates import step_generate_room_templates
from processing.pipeline.types import ProcessingState


def _build_mock_services():
    """Create mock pipeline services."""
    logger = MagicMock()
    logger.info = MagicMock()
    logger.error = MagicMock()
    return {
        "logger": logger,
        "storage": MagicMock(),
    }


def _build_state_with_parsed_data(parsed_data: dict) -> ProcessingState:
    """Build a processing state with parsed JSON data."""
    return {
        "pdf_path": "/test/path/to/drawing.pdf",
        "original_drawing_type": "Architectural",
        "templates_created": {},
        "extraction_result": None,
        "processing_type_for_ai": "Architectural",
        "subtype": None,
        "raw_ai_response_str": None,
        "parsed_json_data": parsed_data,
        "final_status_dict": {"success": True},
        "source_document_info": None,
        "structured_document_info": None,
        "template_files": [],
    }


@pytest.mark.asyncio
async def test_floor_detection_by_filename(tmp_path):
    """Test that floor plan detection works when 'floor' is in filename."""
    parsed_data = {
        "DRAWING_METADATA": {
            "drawing_number": "A2.01",
            "title": "FIRST FLOOR PLAN",
            "project_name": "Test Project",
        },
        "ARCHITECTURAL": {
            "ROOMS": [
                {
                    "room_number": "101",
                    "room_name": "Lobby",
                }
            ]
        },
    }
    
    state = _build_state_with_parsed_data(parsed_data)
    services = _build_mock_services()
    
    # Mock the room_templates module
    mock_result = {
        "e_rooms_file": str(tmp_path / "e_rooms.json"),
        "a_rooms_file": str(tmp_path / "a_rooms.json"),
        "generated_files": [str(tmp_path / "e_rooms.json"), str(tmp_path / "a_rooms.json")],
    }
    
    with mock.patch("templates.room_templates.process_architectural_drawing") as mock_process:
        mock_process.return_value = mock_result
        
        result_state = await step_generate_room_templates(
            state,
            services,
            "/test/path/to/A2.01-floor-plan.pdf",
            "A2.01-floor-plan.pdf",
            str(tmp_path),
            "test-pipeline-id",
            "architectural",
            "a2-01-floor-plan",
            {},
        )
        
        # Should have triggered template generation
        mock_process.assert_called_once()
        assert result_state["templates_created"]["floor_plan"] is True


@pytest.mark.asyncio
async def test_floor_detection_by_metadata_title(tmp_path):
    """Test that floor plan detection works when title contains 'FLOOR' even if filename doesn't."""
    parsed_data = {
        "DRAWING_METADATA": {
            "drawing_number": "A2.01",
            "title": "FLOOR PLAN - LEVEL 3",
            "project_name": "Test Project",
        },
        "ARCHITECTURAL": {
            "ROOMS": [
                {
                    "room_number": "301",
                    "room_name": "Office",
                }
            ]
        },
    }
    
    state = _build_state_with_parsed_data(parsed_data)
    services = _build_mock_services()
    
    mock_result = {
        "e_rooms_file": str(tmp_path / "e_rooms.json"),
        "a_rooms_file": str(tmp_path / "a_rooms.json"),
        "generated_files": [str(tmp_path / "e_rooms.json"), str(tmp_path / "a_rooms.json")],
    }
    
    with mock.patch("templates.room_templates.process_architectural_drawing") as mock_process:
        mock_process.return_value = mock_result
        
        result_state = await step_generate_room_templates(
            state,
            services,
            "/test/path/to/A2.01.pdf",  # No 'floor' in filename
            "A2.01.pdf",
            str(tmp_path),
            "test-pipeline-id",
            "architectural",
            "a2-01",
            {},
        )
        
        # Should have triggered template generation based on metadata title
        mock_process.assert_called_once()
        assert result_state["templates_created"]["floor_plan"] is True


@pytest.mark.asyncio
async def test_floor_detection_by_level_in_title(tmp_path):
    """Test that floor plan detection works when title contains 'LEVEL'."""
    parsed_data = {
        "DRAWING_METADATA": {
            "drawing_number": "A2.02",
            "title": "LEVEL 4 PLAN",
            "project_name": "Test Project",
        },
        "ARCHITECTURAL": {
            "ROOMS": [
                {
                    "room_number": "401",
                    "room_name": "Conference Room",
                }
            ]
        },
    }
    
    state = _build_state_with_parsed_data(parsed_data)
    services = _build_mock_services()
    
    mock_result = {
        "e_rooms_file": str(tmp_path / "e_rooms.json"),
        "a_rooms_file": str(tmp_path / "a_rooms.json"),
        "generated_files": [str(tmp_path / "e_rooms.json"), str(tmp_path / "a_rooms.json")],
    }
    
    with mock.patch("templates.room_templates.process_architectural_drawing") as mock_process:
        mock_process.return_value = mock_result
        
        result_state = await step_generate_room_templates(
            state,
            services,
            "/test/path/to/A2.02.pdf",
            "A2.02.pdf",
            str(tmp_path),
            "test-pipeline-id",
            "architectural",
            "a2-02",
            {},
        )
        
        # Should have triggered template generation based on LEVEL in title
        mock_process.assert_called_once()
        assert result_state["templates_created"]["floor_plan"] is True


@pytest.mark.asyncio
async def test_no_template_generation_for_non_architectural(tmp_path):
    """Test that templates are NOT generated for non-architectural drawings."""
    parsed_data = {
        "DRAWING_METADATA": {
            "drawing_number": "E5.00",
            "title": "PANEL SCHEDULE",
        },
    }
    
    state = _build_state_with_parsed_data(parsed_data)
    state["processing_type_for_ai"] = "Electrical"
    services = _build_mock_services()
    
    with mock.patch("templates.room_templates.process_architectural_drawing") as mock_process:
        result_state = await step_generate_room_templates(
            state,
            services,
            "/test/path/to/E5.00.pdf",
            "E5.00.pdf",
            str(tmp_path),
            "test-pipeline-id",
            "electrical",
            "e5-00",
            {},
        )
        
        # Should NOT have triggered template generation
        mock_process.assert_not_called()
        assert result_state["templates_created"].get("floor_plan") is not True


@pytest.mark.asyncio
async def test_no_template_generation_for_non_floor_plan(tmp_path):
    """Test that templates are NOT generated for architectural drawings that aren't floor plans."""
    parsed_data = {
        "DRAWING_METADATA": {
            "drawing_number": "A3.01",
            "title": "ELEVATION DETAIL",
        },
    }
    
    state = _build_state_with_parsed_data(parsed_data)
    services = _build_mock_services()
    
    with mock.patch("templates.room_templates.process_architectural_drawing") as mock_process:
        result_state = await step_generate_room_templates(
            state,
            services,
            "/test/path/to/A3.01.pdf",
            "A3.01.pdf",
            str(tmp_path),
            "test-pipeline-id",
            "architectural",
            "a3-01",
            {},
        )
        
        # Should NOT have triggered template generation
        mock_process.assert_not_called()
        assert result_state["templates_created"].get("floor_plan") is not True

