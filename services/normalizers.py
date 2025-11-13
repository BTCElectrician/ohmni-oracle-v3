"""
Normalization utilities for structured data.
Extracted from file_processor.py to reduce complexity.

This module now serves as a facade, re-exporting functions from the
domain-specific modules in the normalizers package for backward compatibility.
"""

# Re-export public API functions for backward compatibility
from services.normalizers.electrical import normalize_panel_fields
from services.normalizers.mechanical import normalize_mechanical_schedule
from services.normalizers.plumbing import normalize_plumbing_schedule
from services.normalizers.architectural import normalize_architectural_schedule

__all__ = [
    "normalize_panel_fields",
    "normalize_mechanical_schedule",
    "normalize_plumbing_schedule",
    "normalize_architectural_schedule",
]
