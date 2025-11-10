"""
Thin facade for backward compatibility.

Implementation lives in utils.performance package.
This module maintains the original import path for existing code.
"""
from utils.performance import (
    PerformanceTracker,
    tracker,
    get_tracker,
    time_operation,
    time_operation_context,
)

__all__ = [
    "PerformanceTracker",
    "tracker",
    "get_tracker",
    "time_operation",
    "time_operation_context",
]
