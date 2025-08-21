"""
Main interface module for accessing prompt templates.
"""

from typing import Dict, Optional

# Import prompt dictionaries from each category
from templates.prompts.architectural import ARCHITECTURAL_PROMPTS
from templates.prompts.electrical import ELECTRICAL_PROMPTS
from templates.prompts.mechanical import MECHANICAL_PROMPTS
from templates.prompts.plumbing import PLUMBING_PROMPTS
from templates.prompts.general import GENERAL_PROMPT

# Import registry for more flexible prompt retrieval
from templates.prompt_registry import get_registered_prompt

# Mapping of main drawing types to prompt dictionaries (for backward compatibility)
PROMPT_CATEGORIES = {
    "Architectural": ARCHITECTURAL_PROMPTS,
    "Electrical": ELECTRICAL_PROMPTS,
    "Mechanical": MECHANICAL_PROMPTS,
    "Plumbing": PLUMBING_PROMPTS,
}


def get_prompt_template(drawing_type: str) -> str:
    """
    Get the appropriate prompt template based on drawing type.

    Args:
        drawing_type: Type of drawing (e.g., "Architectural", "Electrical_PanelSchedule")

    Returns:
        Prompt template string appropriate for the drawing type
    """
    # Default to general prompt if no drawing type provided
    if not drawing_type:
        return GENERAL_PROMPT

    # Try to get prompt from registry first (preferred method)
    registered_prompt = get_registered_prompt(drawing_type)
    if registered_prompt:
        return registered_prompt

    # Legacy fallback using dictionaries
    # Parse drawing type to determine category and subtype
    parts = drawing_type.split("_", 1)
    main_type = parts[0]

    # If main type not recognized, return general prompt
    if main_type not in PROMPT_CATEGORIES:
        return GENERAL_PROMPT

    # Get prompt dictionary for this main type
    prompt_dict = PROMPT_CATEGORIES[main_type]

    # Determine subtype (if any)
    subtype = parts[1].upper() if len(parts) > 1 else "DEFAULT"

    # Return the specific subtype prompt if available, otherwise the default for this category
    return prompt_dict.get(subtype, prompt_dict["DEFAULT"])


def get_available_subtypes(main_type: Optional[str] = None) -> Dict[str, list]:
    """
    Get available subtypes for a main drawing type or all types.

    Args:
        main_type: Optional main drawing type (e.g., "Architectural")

    Returns:
        Dictionary of available subtypes by main type
    """
    if main_type and main_type in PROMPT_CATEGORIES:
        # Return subtypes for specific main type
        return {main_type: list(PROMPT_CATEGORIES[main_type].keys())}

    # Return all subtypes by main type
    return {
        category: list(prompts.keys())
        for category, prompts in PROMPT_CATEGORIES.items()
    }
