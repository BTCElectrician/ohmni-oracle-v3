"""
Base templates for construction drawing processing.
Provides reusable prompt templates and formatters.
"""
from templates.prompt_registry import get_registry

registry = get_registry()


def create_general_template(drawing_type: str) -> str:
    """
    Create a basic prompt template for any drawing type.

    Args:
        drawing_type: Type of drawing (e.g., "Electrical")

    Returns:
        Formatted prompt template
    """
    return f"""
    As an expert in {drawing_type} drawings, extract all relevant information 
    from the provided content. Structure your response as a VALID JSON object with:
    
    1. A top level "DRAWING_METADATA" section containing drawing number, title, date, etc.
    2. A main "{drawing_type.upper()}" section with all specific content organized by type.
    3. Appropriate subsections for different component types.
    4. All notes, specifications, and requirements.
    
    Be thorough, accurate, and maintain a consistent structure. Format all field names
    in camelCase, and ensure your entire response is a well-structured, valid JSON object.
    """


def create_schedule_template(schedule_type: str) -> str:
    """
    Create a template for equipment schedules.

    Args:
        schedule_type: Type of schedule (e.g., "Panel")

    Returns:
        Formatted schedule prompt
    """
    return f"""
    Extract the {schedule_type} schedule data from the provided content. 
    Return a VALID JSON object with:
    
    1. A top level "DRAWING_METADATA" section with drawing information.
    2. A main section containing all {schedule_type} data.
    3. Structured representation of all table data preserving all rows and columns.
    4. All relevant notes and specifications.
    
    Ensure your response is a complete, valid JSON object with consistent field names.
    """


# Register the general fallback prompt
registry.register(
    "GENERAL",
    """
    You are an expert in analyzing construction drawings and extracting structured information.
    
    Extract ALL important information from the provided content and structure it into a comprehensive,
    well-organized JSON object. Be thorough and precise.
    
    Your response must be formatted as a valid JSON object with:
    
    1. A top-level "DRAWING_METADATA" object containing:
       - drawing_number: The drawing identifier
       - title: Drawing title/description
       - date: Drawing date if available
       - revision: Revision information if present
       - Other metadata fields as available
    
    2. A main category section based on drawing type (e.g., "ARCHITECTURAL", "ELECTRICAL", "MECHANICAL")
       that contains all extracted information organized into logical subsections.
    
    3. All schedules, notes, specifications, and requirements found in the content.
    
    IMPORTANT: Ensure your entire response is a valid JSON object.
    """,
)
