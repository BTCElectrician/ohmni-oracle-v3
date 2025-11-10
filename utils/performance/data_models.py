"""
Type definitions and data models for performance metrics.
"""
from typing import Dict, Any, List, Optional, TypedDict


class MetricEntry(TypedDict, total=False):
    """Single metric entry structure."""
    file_name: str
    drawing_type: str
    duration: float
    model: Optional[str]
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    is_ocr: Optional[bool]
    api_type: Optional[str]
    reason: Optional[str]
    char_count_total: Optional[int]
    chars_extracted: Optional[int]
    total_chars_after_ocr: Optional[int]
    char_count_threshold: Optional[int]
    threshold_per_page: Optional[int]
    estimated_tokens: Optional[int]
    token_threshold: Optional[int]
    ocr_duration_seconds: Optional[float]
    tiles_processed: Optional[int]
    page_count: Optional[int]
    chars_per_page: Optional[float]
    performed: Optional[bool]
    file_path: Optional[str]
    func_name: Optional[str]


class ApiStats(TypedDict):
    """API statistics structure."""
    min_time: float
    max_time: float
    avg_time: float
    count: int
    total_time: float


class CostEntry(TypedDict):
    """Cost entry structure."""
    total_input_tokens: int
    total_output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float


class FileCostEntry(TypedDict, total=False):
    """File cost entry structure."""
    drawing_type: str
    total_cost: float
    main_cost: float
    ocr_cost: float
    tiles_processed: int


class MetricsDict(Dict[str, List[MetricEntry]]):
    """Dictionary mapping category names to lists of metric entries."""
    pass

