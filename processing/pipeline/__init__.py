"""
Pipeline package for modular PDF processing.

This package contains the refactored pipeline logic, split into focused modules
for better maintainability and LLM comprehension.
"""

from processing.pipeline.orchestrator import process_pipeline
from processing.pipeline.types import ProcessingStatus, ProcessingState, ProcessingResult

__all__ = [
    "process_pipeline",
    "ProcessingStatus",
    "ProcessingState",
    "ProcessingResult",
]

