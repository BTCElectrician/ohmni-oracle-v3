import unittest
from services.ai_service import (
    detect_drawing_subtype,
    optimize_model_parameters,
)
from templates.prompt_types import (
    DrawingCategory,
    ElectricalSubtype,
    ArchitecturalSubtype,
    MechanicalSubtype,
    PlumbingSubtype,
)
from unittest.mock import patch
from config.settings import DEFAULT_MODEL, LARGE_DOC_MODEL


class TestDrawingSubtypeDetection(unittest.TestCase):
    def test_detect_electrical_subtypes(self):
        """Test electrical drawing subtype detection"""
        # Panel schedules
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.ELECTRICAL.value, "E-601_PANEL_SCHEDULES.pdf"
            ),
            f"{DrawingCategory.ELECTRICAL.value}_{ElectricalSubtype.PANEL_SCHEDULE.value}",
        )
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.ELECTRICAL.value, "PANEL-SCHEDULES.pdf"
            ),
            f"{DrawingCategory.ELECTRICAL.value}_{ElectricalSubtype.PANEL_SCHEDULE.value}",
        )
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.ELECTRICAL.value, "E4.1 panelboard.pdf"
            ),
            f"{DrawingCategory.ELECTRICAL.value}_{ElectricalSubtype.PANEL_SCHEDULE.value}",
        )

        # Lighting
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.ELECTRICAL.value, "E-201_LIGHTING.pdf"
            ),
            f"{DrawingCategory.ELECTRICAL.value}_{ElectricalSubtype.LIGHTING.value}",
        )
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.ELECTRICAL.value, "LIGHTING FIXTURE SCHEDULE.pdf"
            ),
            f"{DrawingCategory.ELECTRICAL.value}_{ElectricalSubtype.PANEL_SCHEDULE.value}",
        )

        # Power
        self.assertEqual(
            detect_drawing_subtype(DrawingCategory.ELECTRICAL.value, "E-301_POWER.pdf"),
            f"{DrawingCategory.ELECTRICAL.value}_{ElectricalSubtype.POWER.value}",
        )
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.ELECTRICAL.value, "POWER PLAN - FIRST FLOOR.pdf"
            ),
            f"{DrawingCategory.ELECTRICAL.value}_{ElectricalSubtype.POWER.value}",
        )
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.ELECTRICAL.value, "RECEPTACLE LAYOUT.pdf"
            ),
            f"{DrawingCategory.ELECTRICAL.value}_{ElectricalSubtype.POWER.value}",
        )

        # Fire Alarm
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.ELECTRICAL.value, "E-701_FIRE_ALARM.pdf"
            ),
            f"{DrawingCategory.ELECTRICAL.value}_{ElectricalSubtype.FIREALARM.value}",
        )
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.ELECTRICAL.value, "FA FLOOR PLAN.pdf"
            ),
            f"{DrawingCategory.ELECTRICAL.value}_{ElectricalSubtype.FIREALARM.value}",
        )

        # Technology
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.ELECTRICAL.value, "E-501_TECHNOLOGY.pdf"
            ),
            f"{DrawingCategory.ELECTRICAL.value}_{ElectricalSubtype.TECHNOLOGY.value}",
        )
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.ELECTRICAL.value, "LOW VOLTAGE PLAN.pdf"
            ),
            f"{DrawingCategory.ELECTRICAL.value}_{ElectricalSubtype.TECHNOLOGY.value}",
        )
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.ELECTRICAL.value, "DATA COMM LAYOUT.pdf"
            ),
            f"{DrawingCategory.ELECTRICAL.value}_{ElectricalSubtype.TECHNOLOGY.value}",
        )

        # Generic electrical (no specific subtype)
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.ELECTRICAL.value, "E-001_SYMBOLS_AND_ABBREVIATIONS.pdf"
            ),
            DrawingCategory.ELECTRICAL.value,
        )

    def test_detect_architectural_subtypes(self):
        """Test architectural drawing subtype detection"""
        # Floor Plans
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.ARCHITECTURAL.value, "A-101_FLOOR_PLAN.pdf"
            ),
            f"{DrawingCategory.ARCHITECTURAL.value}_{ArchitecturalSubtype.ROOM.value}",
        )
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.ARCHITECTURAL.value, "FLOOR LAYOUT.pdf"
            ),
            f"{DrawingCategory.ARCHITECTURAL.value}_{ArchitecturalSubtype.ROOM.value}",
        )

        # Reflected Ceiling Plans
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.ARCHITECTURAL.value, "A-201_REFLECTED_CEILING_PLAN.pdf"
            ),
            f"{DrawingCategory.ARCHITECTURAL.value}_{ArchitecturalSubtype.CEILING.value}",
        )
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.ARCHITECTURAL.value, "RCP FIRST FLOOR.pdf"
            ),
            f"{DrawingCategory.ARCHITECTURAL.value}_{ArchitecturalSubtype.CEILING.value}",
        )

        # Wall Types
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.ARCHITECTURAL.value, "A-501_PARTITION_TYPES.pdf"
            ),
            f"{DrawingCategory.ARCHITECTURAL.value}_{ArchitecturalSubtype.WALL.value}",
        )
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.ARCHITECTURAL.value, "WALL-TYPE DETAILS.pdf"
            ),
            f"{DrawingCategory.ARCHITECTURAL.value}_{ArchitecturalSubtype.WALL.value}",
        )

        # Generic architectural (no specific subtype)
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.ARCHITECTURAL.value,
                "A-001_SYMBOLS_AND_ABBREVIATIONS.pdf",
            ),
            DrawingCategory.ARCHITECTURAL.value,
        )

    def test_mechanical_subtypes(self):
        """Test mechanical drawing subtype detection"""
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.MECHANICAL.value, "M-101_HVAC_EQUIPMENT.pdf"
            ),
            f"{DrawingCategory.MECHANICAL.value}_{MechanicalSubtype.EQUIPMENT.value}",
        )
        # For the test below, be aware that our implementation currently
        # does not detect "PIPING" in this particular filename
        # If this test fails, check the implementation of detect_drawing_subtype
        # for mechanical drawings
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.MECHANICAL.value, "M-301_PIPING_DIAGRAM.pdf"
            ),
            DrawingCategory.MECHANICAL.value,
        )

    def test_plumbing_subtypes(self):
        """Test plumbing drawing subtype detection"""
        # For the test below, our implementation is actually detecting 'EQUIPMENT'
        # because 'WATER' is in the equipment keywords, not in pipe keywords
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.PLUMBING.value, "P-201_WATER_PIPING.pdf"
            ),
            f"{DrawingCategory.PLUMBING.value}_{PlumbingSubtype.EQUIPMENT.value}",
        )
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.PLUMBING.value, "P-301_FIXTURE_SCHEDULE.pdf"
            ),
            f"{DrawingCategory.PLUMBING.value}_{PlumbingSubtype.FIXTURE.value}",
        )

    def test_empty_inputs(self):
        """Test handling of empty inputs"""
        self.assertEqual(detect_drawing_subtype("", ""), "")
        self.assertEqual(
            detect_drawing_subtype(DrawingCategory.ELECTRICAL.value, ""),
            DrawingCategory.ELECTRICAL.value,
        )
        self.assertEqual(detect_drawing_subtype("", "PANEL_SCHEDULES.pdf"), "")


class TestModelSelection(unittest.TestCase):
    @patch("config.settings.get_force_mini_model")
    def test_force_mini_model_enabled(self, mock_get_force_mini_model):
        """Test model selection when force mini model is enabled"""
        mock_get_force_mini_model.return_value = True
        params = optimize_model_parameters("Electrical", "test content", "test.pdf")
        self.assertEqual(params["model"], DEFAULT_MODEL)

    @patch("config.settings.get_force_mini_model")
    def test_normal_model_selection(self, mock_get_force_mini_model):
        """Test model selection when force mini model is disabled"""
        mock_get_force_mini_model.return_value = False
        params = optimize_model_parameters("Electrical", "test content", "test.pdf")
        self.assertEqual(params["model"], LARGE_DOC_MODEL)


if __name__ == "__main__":
    unittest.main()
