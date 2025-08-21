import unittest
from templates.prompt_templates import get_prompt_template, get_available_subtypes


class PromptTemplateTests(unittest.TestCase):
    def test_basic_template_retrieval(self):
        """Test that basic template retrieval works for main types."""
        self.assertIsNotNone(get_prompt_template("Electrical"))
        self.assertIsNotNone(get_prompt_template("Architectural"))
        self.assertIsNotNone(get_prompt_template("Mechanical"))
        self.assertIsNotNone(get_prompt_template("Plumbing"))

    def test_subtype_template_retrieval(self):
        """Test that subtype template retrieval works."""
        self.assertIsNotNone(get_prompt_template("Electrical_PANEL_SCHEDULE"))
        self.assertIsNotNone(get_prompt_template("Architectural_ROOM"))

    def test_unknown_type_fallback(self):
        """Test that unknown types fall back to general prompt."""
        general_prompt = get_prompt_template("General")
        unknown_prompt = get_prompt_template("UnknownType")
        self.assertEqual(general_prompt, unknown_prompt)

    def test_available_subtypes(self):
        """Test retrieval of available subtypes."""
        all_subtypes = get_available_subtypes()
        self.assertIn("Electrical", all_subtypes)
        self.assertIn("DEFAULT", all_subtypes["Electrical"])

        electrical_subtypes = get_available_subtypes("Electrical")
        self.assertIn("Electrical", electrical_subtypes)
        self.assertIn("PANEL_SCHEDULE", electrical_subtypes["Electrical"])


if __name__ == "__main__":
    unittest.main()
