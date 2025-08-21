import unittest
from services.ai_service import detect_drawing_subtype
from templates.prompt_types import (
    DrawingCategory,
    ElectricalSubtype,
    ArchitecturalSubtype,
)


class DrawingTypeDetectionTests(unittest.TestCase):
    def test_electrical_panel_detection(self):
        """Test that electrical panel schedules are detected correctly."""
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.ELECTRICAL.value, "K1S_panel_schedule.pdf"
            ),
            f"{DrawingCategory.ELECTRICAL.value}_{ElectricalSubtype.PANEL_SCHEDULE.value}",
        )

    def test_architectural_room_detection(self):
        """Test that architectural floor plans are detected correctly."""
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.ARCHITECTURAL.value, "A101_floor_plan.pdf"
            ),
            f"{DrawingCategory.ARCHITECTURAL.value}_{ArchitecturalSubtype.ROOM.value}",
        )

    def test_specification_detection(self):
        """Test that specifications are detected correctly."""
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.ELECTRICAL.value, "electrical_spec.pdf"
            ),
            DrawingCategory.SPECIFICATIONS.value,
        )

    def test_fallback_to_main_type(self):
        """Test fallback to main type when subtype not detected."""
        self.assertEqual(
            detect_drawing_subtype(
                DrawingCategory.ELECTRICAL.value, "unknown_drawing.pdf"
            ),
            DrawingCategory.ELECTRICAL.value,
        )


if __name__ == "__main__":
    unittest.main()
