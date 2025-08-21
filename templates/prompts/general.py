"""
General prompt templates for construction drawing processing.
"""
from templates.prompt_registry import register_prompt
from templates.base_templates import create_general_template


@register_prompt("General")
def general_prompt():
    """General purpose prompt for any drawing type."""
    return create_general_template(
        drawing_type="construction",
        element_type="construction",
        instructions="""
Extract ALL elements following a logical structure, while adapting to project-specific terminology.
""",
        example="""
{
  "metadata": {
    "drawing_number": "X101",
    "title": "DRAWING TITLE",
    "date": "2023-05-15",
    "revision": "2"
  },
  "schedules": [
    {
      "type": "schedule_type",
      "data": [
        {"item_id": "X1", "description": "Item description", "specifications": "Technical details"}
      ]
    }
  ],
  "notes": ["Note 1", "Note 2"]
}
""",
        context="Engineers need EVERY element and specification value EXACTLY as shown - complete accuracy is essential for proper system design, ordering, and installation.",
    )


# Register general prompt to ensure it's always available
GENERAL_PROMPT = general_prompt()
