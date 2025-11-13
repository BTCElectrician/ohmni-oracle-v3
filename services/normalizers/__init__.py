"""
Normalization utilities package for structured data.

This package provides domain-specific normalization modules:
- electrical: Panel schedules and electrical systems
- mechanical: Equipment schedules and HVAC systems
- plumbing: Fixture, water heater, and piping schedules
- architectural: Finish, door, and window schedules (placeholder)
- common: Shared utility functions
"""

# Re-export public API functions for backward compatibility
from .electrical import normalize_panel_fields
from .mechanical import normalize_mechanical_schedule
from .plumbing import normalize_plumbing_schedule
from .architectural import normalize_architectural_schedule

__all__ = [
    "normalize_panel_fields",
    "normalize_mechanical_schedule",
    "normalize_plumbing_schedule",
    "normalize_architectural_schedule",
]

