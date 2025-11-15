"""Tests for facts fallback iterators when blocks are missing."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

try:
    from tools.schedule_postpass.facts import emit_facts
except ImportError:  # pragma: no cover
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    sys.path.append(str(repo_root))
    from tools.schedule_postpass.facts import emit_facts  # type: ignore


@pytest.fixture
def mock_meta():
    """Standard metadata for test facts."""
    return {
        "tenant_id": "ohmni",
        "project": "Test Project",
        "project_id": "test-proj",
        "sheet_number": "E1.01",
        "sheet_title": "Test Sheet",
        "discipline": "electrical",
        "revision": "A",
        "revision_date": "2024-01-01T00:00:00Z",
        "levels": [],
        "source_file": "test.pdf",
    }


@pytest.fixture
def mock_client():
    """Mock OpenAI client that returns None for embeddings."""
    return None


def test_blocks_precedence_no_fallback(mock_meta, mock_client):
    """When blocks exist, fallbacks should not be used."""
    raw_json = {
        "blocks": [
            {
                "type": "panel schedule",
                "name": "PANEL S1",
                "rows": [
                    {"panel": "S1", "circuit": "1", "load": "Lighting", "amps": "20", "voltage": "120"}
                ],
            }
        ],
        "ELECTRICAL": {
            "panels": [
                {
                    "panel_name": "LP-1",
                    "circuits": [
                        {"circuit_number": "1", "load_name": "Should not appear", "trip": 20}
                    ],
                }
            ]
        },
    }

    facts = list(emit_facts(raw_json, mock_meta, mock_client))
    assert len(facts) == 1
    assert facts[0]["schedule_type"] == "panel"
    assert facts[0]["key"]["panel"] == "S1"
    assert facts[0]["key"]["circuit"] == "1"
    # Verify fallback data didn't leak in
    assert facts[0]["attributes"].get("description") == "Lighting"


def test_electrical_panels_fallback(mock_meta, mock_client):
    """Electrical panels fallback emits panel facts when no blocks."""
    raw_json = {
        "ELECTRICAL": {
            "panels": [
                {
                    "panel_name": "LP-1",
                    "voltage": "120/208V",
                    "circuits": [
                        {"circuit_number": "1", "load_name": "Lighting", "trip": 20, "poles": 1},
                        {"circuit": "3", "description": "Receptacles", "amps": 20},
                    ],
                }
            ]
        }
    }

    facts = list(emit_facts(raw_json, mock_meta, mock_client))
    assert len(facts) == 2
    assert all(f["schedule_type"] == "panel" for f in facts)
    assert facts[0]["key"]["panel"] == "LP-1"
    assert facts[0]["key"]["circuit"] == "1"
    assert facts[1]["key"]["circuit"] == "3"


def test_electrical_panel_schedules_dict_fallback(mock_meta, mock_client):
    """Electrical PANEL_SCHEDULES dict format fallback."""
    raw_json = {
        "ELECTRICAL": {
            "PANEL_SCHEDULES": {
                "S2": {
                    "voltage": "120",
                    "circuit_details": [
                        {"circuit_number": "1", "load_name": "Kitchen", "trip": 20}
                    ],
                }
            }
        }
    }

    facts = list(emit_facts(raw_json, mock_meta, mock_client))
    assert len(facts) == 1
    assert facts[0]["schedule_type"] == "panel"
    assert facts[0]["key"]["panel"] == "S2"
    assert facts[0]["key"]["circuit"] == "1"


def test_mechanical_equipment_fallback(mock_meta, mock_client):
    """Mechanical equipment fallback emits mech_equipment facts."""
    raw_json = {
        "MECHANICAL": {
            "equipment": [
                {"tag": "AHU-1", "voltage": "480", "hp": 10, "mca": 25},
                {"equipment_tag": "RTU-1", "voltage": "208", "kw": 5},
            ]
        }
    }

    facts = list(emit_facts(raw_json, mock_meta, mock_client))
    assert len(facts) == 2
    assert all(f["schedule_type"] == "mech_equipment" for f in facts)
    assert facts[0]["key"]["tag"] == "AHU-1"
    assert facts[1]["key"]["tag"] == "RTU-1"


def test_mechanical_equipment_dict_fallback(mock_meta, mock_client):
    """Mechanical equipment dict-of-lists format."""
    raw_json = {
        "MECHANICAL": {
            "equipment": {
                "airHandlingUnits": [
                    {"tag": "AHU-1", "voltage": "480", "hp": 10},
                ],
                "fans": [
                    {"tag": "EF-1", "voltage": "120", "hp": 1},
                ],
            }
        }
    }

    facts = list(emit_facts(raw_json, mock_meta, mock_client))
    assert len(facts) == 2
    assert all(f["schedule_type"] == "mech_equipment" for f in facts)
    tags = {f["key"]["tag"] for f in facts}
    assert tags == {"AHU-1", "EF-1"}


def test_plumbing_fixtures_fallback(mock_meta, mock_client):
    """Plumbing fixtures fallback emits plumb_equipment facts."""
    raw_json = {
        "PLUMBING": {
            "fixtures": [
                {"fixture_id": "WC-1", "description": "Water Closet", "flow_rate": 1.6},
                {"tag": "LS-1", "description": "Lavatory Sink", "gpm": 2.0},
            ]
        }
    }

    facts = list(emit_facts(raw_json, mock_meta, mock_client))
    assert len(facts) == 2
    assert all(f["schedule_type"] == "plumb_equipment" for f in facts)
    assert facts[0]["key"]["tag"] == "WC-1"
    assert facts[1]["key"]["tag"] == "LS-1"


def test_plumbing_water_heaters_fallback(mock_meta, mock_client):
    """Plumbing water heaters fallback."""
    raw_json = {
        "PLUMBING": {
            "water_heaters": [
                {"heater_id": "WH-1", "capacity": 50, "input": 45000},
            ]
        }
    }

    facts = list(emit_facts(raw_json, mock_meta, mock_client))
    assert len(facts) == 1
    assert facts[0]["schedule_type"] == "plumb_equipment"
    assert facts[0]["key"]["tag"] == "WH-1"


def test_architectural_wall_partition_fallback(mock_meta, mock_client):
    """Architectural wall/partition fallback."""
    raw_json = {
        "ARCHITECTURAL": {
            "WALL_TYPES": [
                {"wall_type": "A-101", "fire_rating": "2HR", "stc": 50},
                {"partition_type": "B-201", "fire_rating": "1HR", "stc": 45},
            ]
        }
    }

    facts = list(emit_facts(raw_json, mock_meta, mock_client))
    assert len(facts) == 2
    assert all(f["schedule_type"] == "wall_partition" for f in facts)
    assert facts[0]["key"]["wall_type"] == "A-101"
    assert facts[1]["key"]["wall_type"] == "B-201"


def test_architectural_door_fallback(mock_meta, mock_client):
    """Architectural door schedule fallback."""
    raw_json = {
        "ARCHITECTURAL": {
            "DOOR_SCHEDULE": [
                {"door_number": "101", "hardware_set": "H1", "fire_rating": "20min"},
                {"mark": "102", "size": "3-0 x 7-0"},
            ]
        }
    }

    facts = list(emit_facts(raw_json, mock_meta, mock_client))
    assert len(facts) == 2
    assert all(f["schedule_type"] == "door" for f in facts)
    assert facts[0]["key"]["door_number"] == "101"
    assert facts[1]["key"]["door_number"] == "102"


def test_architectural_ceiling_fallback(mock_meta, mock_client):
    """Architectural ceiling schedule fallback."""
    raw_json = {
        "ARCHITECTURAL": {
            "CEILING_SCHEDULE": [
                {"ceiling_type": "A", "ceiling_height_in": 96, "acoustic": "NRC 0.70"},
            ]
        }
    }

    facts = list(emit_facts(raw_json, mock_meta, mock_client))
    assert len(facts) == 1
    assert facts[0]["schedule_type"] == "ceiling"
    assert facts[0]["key"]["ceiling_type"] == "A"


def test_architectural_finish_fallback(mock_meta, mock_client):
    """Architectural finish schedule fallback."""
    raw_json = {
        "ARCHITECTURAL": {
            "FINISH_SCHEDULE": [
                {"space": "A101", "finish_floor": "VCT", "finish_wall": "Paint"},
                {"room": "A102", "finish_floor": "Carpet"},
            ]
        }
    }

    facts = list(emit_facts(raw_json, mock_meta, mock_client))
    assert len(facts) == 2
    assert all(f["schedule_type"] == "finish" for f in facts)
    assert facts[0]["key"]["tag"] == "A101"
    assert facts[1]["key"]["tag"] == "A102"


def test_multiple_disciplines_fallback(mock_meta, mock_client):
    """Multiple disciplines emit facts when no blocks."""
    raw_json = {
        "ELECTRICAL": {
            "panels": [
                {
                    "panel_name": "LP-1",
                    "circuits": [{"circuit_number": "1", "load_name": "Lighting", "trip": 20}],
                }
            ]
        },
        "MECHANICAL": {
            "equipment": [{"tag": "AHU-1", "voltage": "480"}]
        },
        "PLUMBING": {
            "fixtures": [{"fixture_id": "WC-1", "description": "Water Closet"}]
        },
        "ARCHITECTURAL": {
            "DOOR_SCHEDULE": [{"door_number": "101", "hardware_set": "H1"}]
        },
    }

    facts = list(emit_facts(raw_json, mock_meta, mock_client))
    assert len(facts) == 4
    schedule_types = {f["schedule_type"] for f in facts}
    assert schedule_types == {"panel", "mech_equipment", "plumb_equipment", "door"}


def test_partial_rows_graceful(mock_meta, mock_client):
    """Partial/missing fields don't crash, still emit minimal facts."""
    raw_json = {
        "ELECTRICAL": {
            "panels": [
                {
                    "panel_name": "LP-1",
                    "circuits": [
                        {"circuit_number": "1"},  # Missing description/amps
                        {"load_name": "Lighting"},  # Missing circuit number
                    ],
                }
            ]
        }
    }

    facts = list(emit_facts(raw_json, mock_meta, mock_client))
    # Should emit at least one fact (the one with circuit_number)
    assert len(facts) >= 1
    assert facts[0]["schedule_type"] == "panel"


def test_empty_json_no_crash(mock_meta, mock_client):
    """Empty JSON doesn't crash."""
    raw_json = {}
    facts = list(emit_facts(raw_json, mock_meta, mock_client))
    assert len(facts) == 0


def test_no_discipline_sections_no_crash(mock_meta, mock_client):
    """JSON without discipline sections doesn't crash."""
    raw_json = {"some_other_key": "value"}
    facts = list(emit_facts(raw_json, mock_meta, mock_client))
    assert len(facts) == 0


def test_electrical_paired_circuits_with_phase_loads_text(mock_meta, mock_client):
    """Test that right_side circuits and descriptive text in phase_loads are captured."""
    raw_json = {
        "ELECTRICAL": {
            "panels": [
                {
                    "panel_name": "L1",
                    "enclosure_info": {
                        "volts": "120/208 Wye"
                    },
                    "circuits": [
                        {
                            "circuit_number": 15,
                            "load_name": "CU-1.2",
                            "trip": "50 A",
                            "poles": 3,
                            "phase_loads": {
                                "A": "11473 VA",
                                "B": "MV-400 (Surge Protector)",
                                "C": None
                            },
                            "right_side": {
                                "circuit_number": 16,
                                "load_name": "CU-1.3",
                                "trip": "50 A",
                                "poles": 3,
                                "phase_loads": {
                                    "A": "20 A",
                                    "B": None,
                                    "C": None
                                }
                            }
                        },
                        {
                            "ckt": "13",
                            "load_name": None,
                            "trip": None,
                            "poles": None,
                            "phase_loads": {
                                "A": "11473 VA",
                                "B": "11473 VA",
                                "C": None
                            },
                            "right_side": {
                                "circuit_number": 14,
                                "load_name": None,
                                "trip": None,
                                "poles": None,
                                "phase_loads": {
                                    "A": None,
                                    "B": None,
                                    "C": None
                                }
                            }
                        }
                    ]
                },
                {
                    "panel_id": "H1",
                    "enclosure_info": {
                        "volts": "480/277 Wye"
                    },
                    "circuits": [
                        {
                            "ckt": "13",
                            "load_name": None,
                            "trip": None,
                            "poles": None,
                            "ckt_b": "14",
                            "load_name_b": None,
                            "trip_b": "20 A",
                            "poles_b": 1,
                            "phase_loads": {
                                "A": "11473 VA",
                                "B": "Surge Protector",
                                "C": None
                            }
                        }
                    ]
                }
            ]
        }
    }

    facts = list(emit_facts(raw_json, mock_meta, mock_client))
    assert len(facts) >= 4  # At least 4 circuits should be emitted
    
    # Verify Panel L1 circuit 15 is emitted
    l1_c15 = next((f for f in facts if f.get("panel_name") == "L1" and f.get("circuit_number") == "15"), None)
    assert l1_c15 is not None
    assert l1_c15["description"] == "CU-1.2"
    
    # Verify Panel L1 circuit 16 (right_side) is emitted
    l1_c16 = next((f for f in facts if f.get("panel_name") == "L1" and f.get("circuit_number") == "16"), None)
    assert l1_c16 is not None
    assert l1_c16["description"] == "CU-1.3"
    
    # Verify Panel L1 circuit 13 is emitted
    l1_c13 = next((f for f in facts if f.get("panel_name") == "L1" and f.get("circuit_number") == "13"), None)
    assert l1_c13 is not None
    
    # Verify Panel L1 circuit 14 (right_side) is emitted
    l1_c14 = next((f for f in facts if f.get("panel_name") == "L1" and f.get("circuit_number") == "14"), None)
    assert l1_c14 is not None
    
    # Verify Panel H1 circuit 13 is emitted
    h1_c13 = next((f for f in facts if f.get("panel_name") == "H1" and f.get("circuit_number") == "13"), None)
    assert h1_c13 is not None
    
    # Verify Panel H1 circuit 14 (from ckt_b) is emitted with surge protector description
    h1_c14 = next((f for f in facts if f.get("panel_name") == "H1" and f.get("circuit_number") == "14"), None)
    assert h1_c14 is not None
    assert "surge" in h1_c14.get("description", "").lower() or "surge" in h1_c14.get("content", "").lower()
    assert h1_c14.get("amps") == "20 A"

