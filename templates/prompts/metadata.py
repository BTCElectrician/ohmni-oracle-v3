"""
Metadata-specific prompt templates for construction drawing processing.
"""
from templates.prompt_registry import register_prompt, get_registry

# Get registry singleton
registry = get_registry()

# Register metadata repair prompt
registry.register(
    "METADATA_REPAIR",
    """
    You are an expert assistant tasked with extracting specific metadata fields from the provided text snippet, which is likely from a drawing's title block.
    Extract the following fields if present in the text. If a field is not present, omit it or set its value to null.
    Your response MUST be a single, valid JSON object containing ONLY a "DRAWING_METADATA" key.
    
    Fields to extract into "DRAWING_METADATA":
    - drawing_number: The primary drawing identifier or sheet number (e.g., "A-101", "E1.0"). This is CRITICAL.
    - title: The main title of the drawing.
    - revision: The revision number or letter (e.g., "3", "B").
    - date: The date of the drawing (e.g., "2023-10-26", "10/26/23").
    - project_name: The name of the overall project.
    - job_number: The project or job number.
    
    Example Output:
    {
      "DRAWING_METADATA": {
        "drawing_number": "E-101",
        "title": "FIRST FLOOR POWER PLAN",
        "revision": "A",
        "date": "2024-01-15",
        "project_name": "COMMERCIAL BUILDING XYZ",
        "job_number": "P2023-007"
      }
    }
    
    If the text is "Drawing E-101, Rev A, Project Alpha", your output should be:
    {
      "DRAWING_METADATA": {
        "drawing_number": "E-101",
        "revision": "A",
        "project_name": "Project Alpha"
      }
    }
    
    Focus ONLY on these metadata fields. Do not extract other information.
    Ensure the output is valid JSON.
    """,
    aliases=["METADATA", "META_REPAIR"],
) 