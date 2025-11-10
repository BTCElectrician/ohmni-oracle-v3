"""
Performance tracking package.

This package provides performance tracking utilities for monitoring
processing operations, API calls, and cost analysis.
"""
from utils.performance.tracker import PerformanceTracker
from utils.performance.decorators import time_operation, time_operation_context
from utils.performance.tracker import get_tracker

# Create a global instance for backward compatibility
tracker = PerformanceTracker()

__all__ = [
    "PerformanceTracker",
    "tracker",
    "get_tracker",
    "time_operation",
    "time_operation_context",
]

