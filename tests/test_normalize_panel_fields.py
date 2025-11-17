import copy

from services.normalizers import normalize_panel_fields


def _panel_with_circuits(circuits):
    return {
        "ELECTRICAL": {
            "panels": [
                {
                    "panel_name": "K1",
                    "circuits": copy.deepcopy(circuits),
                }
            ]
        }
    }


def _circuit(num, name):
    return {
        "circuit_number": num,
        "load_name": name,
        "trip": "20 A",
        "poles": 1,
        "phase_loads": {"A": None, "B": None, "C": None},
    }


def test_normalize_pairs_even_into_right_side():
    parsed = _panel_with_circuits(
        [
            _circuit(1, "Left 1"),
            _circuit(2, "Right 2"),
            _circuit(3, "Left 3"),
            _circuit(4, "Right 4"),
        ]
    )

    result = normalize_panel_fields(copy.deepcopy(parsed))
    circuits = result["ELECTRICAL"]["panels"][0]["circuits"]

    assert len(circuits) == 2
    assert circuits[0]["circuit_number"] == 1
    assert circuits[0]["right_side"]["circuit_number"] == 2
    assert circuits[1]["circuit_number"] == 3
    assert circuits[1]["right_side"]["circuit_number"] == 4


def test_normalize_preserves_unpaired_even():
    parsed = _panel_with_circuits([_circuit(2, "Even without left")])

    result = normalize_panel_fields(copy.deepcopy(parsed))
    circuits = result["ELECTRICAL"]["panels"][0]["circuits"]

    assert len(circuits) == 1
    assert circuits[0]["circuit_number"] == 2
    assert "right_side" not in circuits[0]

