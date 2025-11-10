import json
from pathlib import Path

from templates.room_templates import process_architectural_drawing


def _build_sample_parsed_data():
    return {
        "DRAWING_METADATA": {
            "drawing_number": "A2.2",
            "title": "DIMENSION FLOOR PLAN REV.3",
            "project_name": "Sample Project",
        },
        "ARCHITECTURAL": {
            "ROOMS": [
                {
                    "room_number": "101",
                    "room_name": "Lobby",
                    "area": "120 sqft",
                }
            ]
        },
    }


def test_process_architectural_drawing_creates_template_files(tmp_path: Path):
    parsed = _build_sample_parsed_data()
    pdf_path = tmp_path / "A2.2-DIMENSION-FLOOR-PLAN-Rev.3.pdf"
    pdf_path.write_bytes(b"%PDF-1.7 test")

    result = process_architectural_drawing(parsed, str(pdf_path), str(tmp_path))

    e_file = Path(result["e_rooms_file"])
    a_file = Path(result["a_rooms_file"])

    assert e_file.exists(), "Electrical room template was not written"
    assert a_file.exists(), "Architectural room template was not written"

    with e_file.open() as handle:
        e_payload = json.load(handle)

    assert e_payload["rooms"], "Room template should include at least one room"
    assert e_payload["metadata"]["drawing_number"] == "A2.2"

    assert "generated_files" in result and len(result["generated_files"]) == 2
