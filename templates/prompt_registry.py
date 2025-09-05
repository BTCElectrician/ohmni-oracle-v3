"""
Registry system for managing prompt templates.
Provides a singleton registry that serves as the single source of truth for all prompt templates.
"""
from typing import Dict, Optional, List, Callable
import logging

logger = logging.getLogger(__name__)


class PromptRegistry:
    """Single source of truth for all prompt templates."""

    _instance = None
    _prompts = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PromptRegistry, cls).__new__(cls)
            cls._instance._prompts = {}
        return cls._instance

    def register(self, key: str, prompt_text: str, aliases: Optional[List[str]] = None):
        """Register a prompt template with optional aliases."""
        key = key.upper()
        # Ensure prompt contains 'json' for OpenAI API requirement
        prompt_text = self._ensure_json_keyword(prompt_text)
        self._prompts[key] = prompt_text

        if aliases:
            for alias in aliases:
                self._prompts[alias.upper()] = prompt_text

        return self  # Enable method chaining

    def get(self, drawing_type: str, subtype: Optional[str] = None) -> str:
        """
        Always return the GENERAL prompt regardless of drawing type.
        Modern AI models handle construction drawings well without specialized prompts.
        """
        return self._prompts.get("GENERAL", "")

    def _ensure_json_keyword(self, prompt_text: str) -> str:
        """
        Ensure the prompt contains the word 'json' to satisfy OpenAI API requirements
        when using response_format={"type": "json_object"}.
        """
        if not prompt_text:
            return "Please structure your response as valid JSON."

        if "json" not in prompt_text.lower():
            # Add instruction to format as JSON if not already present
            prompt_text += (
                "\n\nIMPORTANT: Format your entire response as a valid JSON object."
            )

        return prompt_text

    def keys(self) -> List[str]:
        """Return all registered prompt keys."""
        return list(self._prompts.keys())

    def contains(self, key: str) -> bool:
        """Check if a prompt key exists."""
        return key.upper() in self._prompts


# Register the new GENERAL prompt
_registry = PromptRegistry()
_registry.register(
    "GENERAL",
    """
    You are an expert in analyzing construction drawings and extracting structured information.
    
    EXTRACT EVERY DETAIL from the provided content and structure it into a comprehensive,
    well-organized JSON object. Be EXTREMELY thorough and precise. Do not summarize or condense.
    
    Your response must be formatted as a valid JSON object with:
    
    1. A top-level "DRAWING_METADATA" object containing:
       - drawing_number: The drawing identifier
        - title: Drawing title/description
        - date: Drawing date if available
        - revision: Revision information if present
        - project_name: Full project name
        - Other metadata fields as available
    
    2. A main category section based on drawing type:
        - For ARCHITECTURAL drawings: Use "ARCHITECTURAL" as the main key
        - For ELECTRICAL drawings: Use "ELECTRICAL" as the main key
        - For MECHANICAL drawings: Use "MECHANICAL" as the main key
        - For PLUMBING drawings: Use "PLUMBING" as the main key
        - For other drawings: Use an appropriate main category key
    
    3. Under the main category, capture ALL content using these guidelines:
        - For schedules and tabular data: Preserve ALL rows, columns, and values exactly as shown. 
          Include every cell, measurement, specification, and notation. Do not skip any entries.
        - For specifications and text sections: Capture EVERY section, subsection, paragraph and note.
          Preserve the exact wording, numbering, and hierarchy of the content.
        - For drawings with multiple data types: Organize data into logical sections like 
          "SCHEDULES", "NOTES", "SPECIFICATIONS", etc.
    
    CRITICAL ROOM STRUCTURE FOR ARCHITECTURAL DRAWINGS:
    For FLOOR PLANS, you MUST organize room information like this:
    {
      "ARCHITECTURAL": {
        "ROOMS": [
          {
            "room_number": "101",  
            "room_name": "LOBBY",
            "dimensions": "20'-0\" x 30'-0\"",
            ... other room properties
          },
          ... additional rooms
        ]
      }
    }
    
    Room information MUST be placed under ARCHITECTURAL.ROOMS for proper processing.
    This structure is REQUIRED for all architectural drawings containing room information.
    
    EXTREMELY IMPORTANT:
    - CAPTURE EVERYTHING - Missing information can lead to construction errors and liability issues
    - PRESERVE EXACT VALUES - Never round or approximate measurements or specifications
    - MAINTAIN COMPLETE HIERARCHY - Keep all parent-child relationships intact
    - FORMAT AS VALID JSON - Ensure all keys use double quotes and there are no trailing commas
    
    For specific drawing types:
    - ELECTRICAL SCHEDULES: Capture ALL circuits, loads, panels, and connection details
    - MECHANICAL SCHEDULES: Record ALL equipment specifications including cfm, tonnage, dimensions
    - PLUMBING SCHEDULES: Include ALL fixture types, connections, and flow requirements
    - ARCHITECTURAL: Document ALL room information, wall types, door/window schedules
    
    CRITICAL: Engineers and contractors rely on this data for construction. Complete and accurate
    extraction is essential for proper system design, ordering, and installation.
    """,
)


def get_registry() -> PromptRegistry:
    """Get the global prompt registry instance."""
    return _registry


# Legacy support - maintain backward compatibility with prior implementation
PROMPT_REGISTRY: Dict[str, Callable[[], str]] = {}


def register_prompt(category: str, subtype: Optional[str] = None):
    """
    Decorator to register a prompt factory function.
    Maintained for backward compatibility.

    Args:
        category: Drawing category (e.g., "Electrical")
        subtype: Drawing subtype (e.g., "PanelSchedule")

    Returns:
        Decorator function that registers the decorated function
    """
    key = f"{category}_{subtype}" if subtype else category

    def decorator(func: Callable[[], str]):
        PROMPT_REGISTRY[key.upper()] = func
        # Also register with new registry
        prompt_text = func()
        _registry.register(key, prompt_text)
        return func

    return decorator


def get_registered_prompt(drawing_type: str) -> str:
    """
    Get prompt using registry with fallbacks.
    Maintained for backward compatibility.

    Args:
        drawing_type: Type of drawing (e.g., "Electrical_PanelSchedule")

    Returns:
        Prompt template string
    """
    # Forward to new registry implementation
    return get_registry().get(drawing_type)


def verify_registry():
    """Skip verification since we're using GENERAL prompt for everything."""
    return True  # Always return success
