"""
Performance tracking utilities.
"""
import time
import asyncio
import logging
import os
import json
import inspect
from typing import (
    Dict,
    Any,
    List,
    Optional,
    TypeVar,
    Tuple,
)
from functools import wraps
from contextlib import contextmanager

T = TypeVar("T")


def _default_pricing_table() -> Dict[str, Dict[str, float]]:
    """Base Tier 4 pricing (USD per 1M tokens) with GPT-4.1 defaults."""
    base = {
        "gpt-4.1": {"input": 3.00, "output": 12.00},
        "gpt-4.1-mini": {"input": 0.80, "output": 3.20},
        "gpt-4.1-nano": {"input": 0.20, "output": 0.80},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o-mini-ocr": {"input": 0.15, "output": 0.60},
    }
    # Mirror pricing for GPT-5 family until official Tier-4 rates are published
    base["gpt-5"] = dict(base["gpt-4.1"])
    base["gpt-5-mini"] = dict(base["gpt-4.1-mini"])
    base["gpt-5-nano"] = dict(base["gpt-4.1-nano"])
    base["gpt-5o"] = dict(base["gpt-4.1"])
    base["gpt-5o-mini"] = dict(base["gpt-4o-mini"])
    return base


def _load_pricing_table() -> Dict[str, Dict[str, float]]:
    """Load Tier-4 pricing table with optional JSON overrides."""
    table = _default_pricing_table()
    override_raw = os.getenv("METRIC_PRICING_OVERRIDES")
    if not override_raw:
        return table

    try:
        overrides = json.loads(override_raw)
        if isinstance(overrides, dict):
            for model, values in overrides.items():
                if not isinstance(values, dict):
                    continue
                input_price = float(values.get("input", 0.0))
                output_price = float(values.get("output", 0.0))
                table[model] = {"input": input_price, "output": output_price}
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "METRIC_PRICING_OVERRIDES invalid JSON - using defaults (%s)", exc
        )
    return table


PRICING_TIER_4 = _load_pricing_table()
TIER4_MONTHLY_LIMIT = float(os.getenv("TIER4_MONTHLY_LIMIT", "5000"))
WORKDAY_HOURS = float(os.getenv("METRICS_WORKDAY_HOURS", "8"))
WORKDAYS_PER_MONTH = float(os.getenv("METRICS_WORKDAYS_PER_MONTH", "20"))
STORAGE_PER_1000_FILES_GB = float(os.getenv("METRICS_STORAGE_PER_1000_FILES_GB", "12.5"))
AZURE_STORAGE_COST_PER_GB = float(os.getenv("METRICS_STORAGE_COST_PER_GB", "0.20"))
METRICS_AVG_CHARS_PER_TOKEN = float(os.getenv("METRICS_AVG_CHARS_PER_TOKEN", "4"))
BASELINE_AVG_TIME = float(os.getenv("METRICS_BASELINE_AVG_TIME", "86.62"))
BASELINE_DATE = os.getenv("METRICS_BASELINE_DATE", "2025-11-09")
BASELINE_ACCEPTABLE_MIN = float(os.getenv("METRICS_BASELINE_MIN", "85"))
BASELINE_ACCEPTABLE_MAX = float(os.getenv("METRICS_BASELINE_MAX", "105"))
BASELINE_COST_PER_DRAWING = float(os.getenv("METRICS_BASELINE_COST_PER_DRAWING", "0.04"))


class PerformanceTracker:
    """
    Tracks performance metrics for different operations.
    """

    def __init__(self):
        # Add new categories for tracking
        self.metrics = {
            "extraction": [],
            "ai_processing": [],
            "api_request": [],  # New category for API calls only
            "json_parsing": [],  # New category for JSON parsing
            "normalization": [],  # New category for data normalization
            "queue_waiting": [],  # New category for queue waiting time
            "extraction_pdf_read": [],  # New subcategory for PDF reading
            "total_processing": [],
            "ocr_processing": [],  # New category for OCR operations
            "ocr_decision": [],  # New category for OCR decision metrics
            "api_cache_hit": [],  # New category for cache hits (separate from live API)
        }

        # Add metrics for tracking API variability
        self.api_stats = {
            "min_time": float("inf"),
            "max_time": 0,
            "total_time": 0,
            "count": 0,
        }
        self.logger = logging.getLogger(__name__)

    def add_metric(
        self, category: str, file_name: str, drawing_type: str, duration: float
    ):
        """
        Add a performance metric.

        Args:
            category: Category of the operation (extraction, ai_processing, etc.)
            file_name: Name of the file being processed
            drawing_type: Type of drawing
            duration: Duration in seconds
        """
        if category not in self.metrics:
            self.metrics[category] = []

        self.metrics[category].append(
            {"file_name": file_name, "drawing_type": drawing_type, "duration": duration}
        )

    def add_api_metric(self, duration: float):
        """
        Record API request timing statistics.

        Args:
            duration: Duration of the API request in seconds
        """
        self.api_stats["min_time"] = min(self.api_stats["min_time"], duration)
        self.api_stats["max_time"] = max(self.api_stats["max_time"], duration)
        self.api_stats["total_time"] += duration
        self.api_stats["count"] += 1

    def add_metric_with_context(
        self, 
        category: str, 
        duration: float,
        file_path: Optional[str] = None,
        drawing_type: Optional[str] = None,
        **kwargs
    ):
        """
        Add a metric with explicit context.
        
        Notes:
        - When category == "api_request", this method also updates aggregate API stats
          (min/max/avg/count/total_time) internally by calling add_api_metric().
          Do NOT call add_api_metric() separately for the same event, or API metrics
          will be double-counted.
          
        Args:
            category: Category name for the metric (e.g., 'extraction', 'api_request')
            duration: Duration of the operation in seconds
            file_path: Optional path to the file being processed
            drawing_type: Optional type of drawing being processed
            **kwargs: Additional context fields to store with the metric
        """
        file_name = os.path.basename(file_path) if file_path else "unknown"
        drawing_type = drawing_type or "unknown"
        
        if category not in self.metrics:
            self.metrics[category] = []
            
        self.metrics[category].append({
            "file_name": file_name,
            "drawing_type": drawing_type,
            "duration": duration,
            **kwargs
        })
        
        # Special handling for API metrics
        if category == "api_request":
            self.add_api_metric(duration)

    def get_api_stats(self):
        """
        Get API request statistics.

        Returns:
            Dictionary of API request statistics
        """
        if self.api_stats["count"] == 0:
            return {
                "min_time": 0,
                "max_time": 0,
                "avg_time": 0,
                "count": 0,
                "total_time": 0,
            }

        return {
            "min_time": self.api_stats["min_time"],
            "max_time": self.api_stats["max_time"],
            "avg_time": self.api_stats["total_time"] / self.api_stats["count"],
            "count": self.api_stats["count"],
            "total_time": self.api_stats["total_time"],
        }

    def get_average_duration(
        self, category: str, drawing_type: Optional[str] = None
    ) -> float:
        """
        Get the average duration for a category.

        Args:
            category: Category of the operation
            drawing_type: Optional drawing type filter

        Returns:
            Average duration in seconds
        """
        if category not in self.metrics:
            return 0.0

        metrics = self.metrics[category]
        if drawing_type:
            metrics = [m for m in metrics if m["drawing_type"] == drawing_type]

        if not metrics:
            return 0.0

        return sum(m["duration"] for m in metrics) / len(metrics)

    def get_slowest_operations(
        self, category: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get the slowest operations for a category.

        Args:
            category: Category of the operation
            limit: Maximum number of results

        Returns:
            List of slow operations
        """
        if category not in self.metrics:
            return []

        return sorted(
            self.metrics[category], key=lambda m: m["duration"], reverse=True
        )[:limit]

    @staticmethod
    def _is_ocr_metric_entry(metric: Dict[str, Any]) -> bool:
        """Detect if an API metric came from the OCR subsystem."""
        if not metric:
            return False

        if metric.get("is_ocr"):
            return True

        api_type = (metric.get("api_type") or "").lower()
        if api_type.startswith("ocr"):
            return True

        model_name = (metric.get("model") or "").lower()
        return model_name.endswith("-ocr") or "ocr" in model_name

    def _calculate_cost_analysis(self) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
        """Aggregate per-model and per-file cost data."""

        def new_cost_entry():
            return {
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "input_cost": 0.0,
                "output_cost": 0.0,
                "total_cost": 0.0,
            }

        by_model: Dict[str, Dict[str, Any]] = {
            model: new_cost_entry() for model in PRICING_TIER_4
        }
        file_costs: Dict[str, Dict[str, Any]] = {}
        api_metrics = self.metrics.get("api_request", [])

        main_total = 0.0
        ocr_total = 0.0

        for metric in api_metrics:
            model = metric.get("model") or "unknown"
            prompt_tokens = int(metric.get("prompt_tokens") or 0)
            completion_tokens = int(metric.get("completion_tokens") or 0)
            pricing = PRICING_TIER_4.get(model, {"input": 0.0, "output": 0.0})
            input_cost = (prompt_tokens / 1_000_000) * pricing.get("input", 0.0)
            output_cost = (completion_tokens / 1_000_000) * pricing.get("output", 0.0)
            total_cost = input_cost + output_cost

            entry = by_model.setdefault(model, new_cost_entry())
            entry["total_input_tokens"] += prompt_tokens
            entry["total_output_tokens"] += completion_tokens
            entry["input_cost"] += input_cost
            entry["output_cost"] += output_cost
            entry["total_cost"] += total_cost

            file_name = metric.get("file_name") or metric.get("file_path") or "unknown"
            file_entry = file_costs.setdefault(
                file_name,
                {
                    "drawing_type": metric.get("drawing_type", "unknown"),
                    "total_cost": 0.0,
                    "main_cost": 0.0,
                    "ocr_cost": 0.0,
                    "tiles_processed": 0,
                },
            )
            if (
                file_entry.get("drawing_type") in (None, "unknown")
                and metric.get("drawing_type")
            ):
                file_entry["drawing_type"] = metric.get("drawing_type")

            file_entry["total_cost"] += total_cost

            if self._is_ocr_metric_entry(metric):
                file_entry["ocr_cost"] += total_cost
                file_entry["tiles_processed"] += 1
                ocr_total += total_cost
            else:
                file_entry["main_cost"] += total_cost
                main_total += total_cost

        grand_total = main_total + ocr_total
        files_processed = len(self.metrics.get("total_processing", []))
        cost_per_drawing = (grand_total / files_processed) if files_processed else 0.0
        cost_per_1000 = cost_per_drawing * 1000
        percent_limit = (
            (grand_total / TIER4_MONTHLY_LIMIT) * 100 if TIER4_MONTHLY_LIMIT else 0.0
        )

        cost_summary = {
            "main_processing_total": main_total,
            "ocr_total": ocr_total,
            "grand_total": grand_total,
            "cost_per_drawing": cost_per_drawing,
            "cost_per_1000_drawings": cost_per_1000,
            "percent_of_5000_tier4_limit": percent_limit,
        }

        cost_analysis = {
            "tier_4_pricing": PRICING_TIER_4,
            "by_model": by_model,
            "cost_summary": cost_summary,
        }

        return cost_analysis, file_costs

    @staticmethod
    def _normalize_ocr_reason(reason: Optional[str]) -> str:
        """Convert free-form OCR reason strings into stable enums."""
        if not reason:
            return "unknown"

        text = " ".join(str(reason).strip().lower().split())
        if not text:
            return "unknown"

        mappings = [
            ("force_panel", "forced_panel_ocr"),
            ("low density", "char_density_low"),
            ("needs ocr", "char_density_low"),
            ("minimal text", "low_total_chars"),
            ("sufficient text", "sufficient_text"),
            ("ocr disabled", "ocr_disabled"),
            ("disabled in configuration", "ocr_disabled"),
            ("ocr failed", "ocr_failure"),
            ("skipped", "skipped"),
        ]

        for needle, label in mappings:
            if needle in text:
                return label

        # Fallback: sanitize original reason into slug form
        sanitized = "".join(ch if ch.isalnum() else "_" for ch in text)
        sanitized = "_".join(filter(None, sanitized.split("_")))
        return sanitized or "unknown"

    def _build_ocr_decision_log(
        self, file_costs: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Summarize OCR trigger decisions per file."""
        ocr_metrics = self.metrics.get("ocr_decision", [])
        by_file: List[Dict[str, Any]] = []

        for metric in ocr_metrics:
            file_name = metric.get("file_name") or metric.get("file_path") or "unknown"
            ocr_triggered = bool(metric.get("performed"))
            file_cost_entry = file_costs.get(file_name, {})

            char_count = metric.get("char_count_total")
            if char_count is None:
                char_count = metric.get("chars_extracted")
            if char_count is None:
                char_count = metric.get("total_chars_after_ocr")

            char_threshold = metric.get("char_count_threshold")
            if char_threshold is None:
                char_threshold = metric.get("threshold_per_page")

            estimated_tokens = metric.get("estimated_tokens")
            if estimated_tokens is None:
                chars = char_count or 0
                estimated_tokens = (
                    int(chars / METRICS_AVG_CHARS_PER_TOKEN) if chars else 0
                )

            reason_detail = metric.get("reason")
            trigger_reason = self._normalize_ocr_reason(reason_detail)

            log_entry = {
                "file_name": file_name,
                "drawing_type": metric.get("drawing_type", "unknown"),
                "ocr_triggered": ocr_triggered,
                "trigger_reason": trigger_reason,
                "reason_detail": reason_detail,
                "char_count": char_count,
                "char_threshold": char_threshold,
                # Backward-compatible fields
                "char_count_total": char_count,
                "char_count_threshold": char_threshold,
                "estimated_tokens": estimated_tokens,
                "token_threshold": metric.get("token_threshold", 0),
                "ocr_duration_sec": metric.get("ocr_duration_seconds"),
                "ocr_cost": file_cost_entry.get("ocr_cost", 0.0),
                "tiles_processed": metric.get(
                    "tiles_processed", file_cost_entry.get("tiles_processed", 0)
                ),
                "page_count": metric.get("page_count"),
                "chars_per_page": metric.get("chars_per_page"),
            }
            by_file.append(log_entry)

        if not by_file and file_costs:
            for file_name, data in file_costs.items():
                by_file.append(
                    {
                        "file_name": file_name,
                        "drawing_type": data.get("drawing_type", "unknown"),
                        "ocr_triggered": data.get("ocr_cost", 0.0) > 0.0,
                        "trigger_reason": "missing_metrics",
                        "reason_detail": "No OCR decision metrics recorded for this file",
                        "char_count": None,
                        "char_threshold": None,
                        "ocr_cost": data.get("ocr_cost", 0.0),
                        "tiles_processed": data.get("tiles_processed", 0),
                    }
                )

        total = len(by_file)
        triggered = sum(1 for entry in by_file if entry.get("ocr_triggered"))
        skipped = max(total - triggered, 0)
        summary = {
            "total_files": total,
            "triggered_ocr": triggered,
            "skipped_ocr": skipped,
            "ocr_trigger_rate_percent": (triggered / total * 100) if total else 0.0,
        }

        return {"summary": summary, "by_file": by_file}

    def _build_drawing_type_costs(
        self,
        file_costs: Dict[str, Dict[str, Any]],
        ocr_log: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Aggregate cost + OCR trigger rate per drawing type."""
        entries = list((ocr_log or {}).get("by_file", []))
        if not entries and file_costs:
            for file_name, data in file_costs.items():
                entries.append(
                    {
                        "file_name": file_name,
                        "drawing_type": data.get("drawing_type", "unknown"),
                        "ocr_triggered": False,
                    }
                )

        type_stats: Dict[str, Dict[str, Any]] = {}
        for entry in entries:
            drawing_type = entry.get("drawing_type") or "Unknown"
            stats = type_stats.setdefault(
                drawing_type,
                {
                    "count": 0,
                    "total_cost": 0.0,
                    "ocr_triggers": 0,
                    "most_expensive_file": None,
                    "max_cost": 0.0,
                },
            )
            file_cost = file_costs.get(entry.get("file_name", ""), {}).get("total_cost", 0.0)
            stats["count"] += 1
            stats["total_cost"] += file_cost
            if entry.get("ocr_triggered"):
                stats["ocr_triggers"] += 1
            if file_cost > stats["max_cost"]:
                stats["max_cost"] = file_cost
                stats["most_expensive_file"] = entry.get("file_name")

        by_type: Dict[str, Dict[str, Any]] = {}
        for drawing_type, stats in type_stats.items():
            count = stats["count"] or 1
            avg_cost = stats["total_cost"] / count
            trigger_rate = stats["ocr_triggers"] / count
            by_type[drawing_type] = {
                "count": stats["count"],
                "total_cost": stats["total_cost"],
                "avg_cost_per_drawing": avg_cost,
                "ocr_trigger_rate": trigger_rate,
            }
            if stats["most_expensive_file"]:
                by_type[drawing_type]["most_expensive_file"] = stats["most_expensive_file"]

        insight = "No drawing cost data collected yet."
        if by_type:
            top_type, top_stats = max(
                by_type.items(), key=lambda item: item[1].get("avg_cost_per_drawing", 0.0)
            )
            insight = (
                f"{top_type} drawings have the highest avg cost (${top_stats['avg_cost_per_drawing']:.2f}) "
                f"with an OCR trigger rate of {top_stats['ocr_trigger_rate'] * 100:.0f}%."
            )

        return {"by_type": by_type, "insight": insight}

    def _build_scaling_projections(self, cost_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Project throughput and spend at larger scales."""
        total_processing = self.metrics.get("total_processing", [])
        files_processed = len(total_processing)
        total_time = sum(m.get("duration", 0.0) for m in total_processing)
        avg_time = (total_time / files_processed) if files_processed else 0.0

        cost_summary = cost_analysis.get("cost_summary", {})
        total_cost = cost_summary.get("grand_total", 0.0)
        cost_per_file = cost_summary.get("cost_per_drawing", 0.0)

        files_per_hour = (3600 / avg_time) if avg_time > 0 else 0.0
        files_per_day = files_per_hour * WORKDAY_HOURS
        files_per_month = files_per_day * WORKDAYS_PER_MONTH

        cost_per_hour = cost_per_file * files_per_hour
        cost_per_day = cost_per_hour * WORKDAY_HOURS
        cost_per_month = cost_per_day * WORKDAYS_PER_MONTH
        months_until_limit = (
            (TIER4_MONTHLY_LIMIT / cost_per_month) if cost_per_month > 0 else 0.0
        )

        current_run = {
            "files_processed": files_processed,
            "total_time_seconds": total_time,
            "avg_time_per_file": avg_time,
            "total_cost": total_cost,
            "cost_per_file": cost_per_file,
        }

        extrapolated = {
            "files_per_hour": files_per_hour,
            "files_per_8hr_workday": files_per_day,
            "files_per_20_workday_month": files_per_month,
            "cost_per_hour": cost_per_hour,
            "cost_per_day": cost_per_day,
            "cost_per_month": cost_per_month,
            "months_until_tier4_limit_reached": months_until_limit,
            "storage_per_1000_files_gb": STORAGE_PER_1000_FILES_GB,
            "estimated_azure_storage_cost_per_month": STORAGE_PER_1000_FILES_GB * AZURE_STORAGE_COST_PER_GB,
        }

        return {"current_run": current_run, "extrapolated": extrapolated}

    def _build_baseline_comparison(
        self,
        scaling: Dict[str, Any],
        ocr_log: Dict[str, Any],
        drawing_type_costs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compare current performance vs. baseline targets."""
        current_run = scaling.get("current_run", {})
        files_processed = current_run.get("files_processed", 0)
        current_avg = current_run.get("avg_time_per_file", 0.0)
        delta_time = current_avg - BASELINE_AVG_TIME if files_processed else 0.0
        percent_diff = (
            (delta_time / BASELINE_AVG_TIME) * 100 if BASELINE_AVG_TIME else 0.0
        )

        in_range = (
            BASELINE_ACCEPTABLE_MIN <= current_avg <= BASELINE_ACCEPTABLE_MAX
            if files_processed
            else True
        )
        delta_section = {
            "time_difference": delta_time,
            "percent_slower": percent_diff,
            "status": "✅ Within acceptable range" if in_range else "❌ Outside acceptable range",
            "acceptable_range": f"{BASELINE_ACCEPTABLE_MIN:.0f}-{BASELINE_ACCEPTABLE_MAX:.0f} sec/drawing",
            "in_range": in_range,
        }

        ocr_rate = (ocr_log.get("summary", {}).get("ocr_trigger_rate_percent", 0.0) if ocr_log else 0.0)
        by_type = (drawing_type_costs or {}).get("by_type", {})
        top_type = None
        if by_type:
            top_type = max(
                by_type.items(),
                key=lambda item: item[1].get("avg_cost_per_drawing", 0.0),
            )[0]

        if not files_processed:
            recommendation = "Run at least one drawing to capture a current baseline."
        elif not in_range and ocr_rate > 30:
            focus = top_type or "the heaviest discipline"
            recommendation = (
                f"OCR overhead ({ocr_rate:.1f}% trigger rate) is pushing run time up. "
                f"Inspect {focus} drawings for unnecessary OCR triggers."
            )
        elif not in_range:
            recommendation = "Average time exceeds the baseline range. Review the slowest files for bottlenecks."
        elif percent_diff < -10:
            recommendation = "Processing is faster than baseline—consider refreshing the baseline if this trend holds."
        else:
            recommendation = "Performance is stable. Continue collecting data to build a trend line."

        current_status = "collecting_trend_data" if files_processed < 10 else "tracking_velocity"
        cost_per_file = current_run.get("cost_per_file") or BASELINE_COST_PER_DRAWING
        cost_notes = (
            "First time tracking costs" if current_run.get("cost_per_file") else "Using baseline estimate"
        )

        return {
            "baseline": {
                "avg_time_per_drawing": BASELINE_AVG_TIME,
                "baseline_date": BASELINE_DATE,
                "status": "established",
            },
            "current": {
                "avg_time_per_drawing": current_avg,
                "status": current_status,
            },
            "delta": delta_section,
            "cost_baseline": {
                "cost_per_drawing": cost_per_file,
                "notes": cost_notes,
            },
            "recommendation": recommendation,
        }
    def report(self):
        """
        Generate a report of performance metrics.

        Returns:
            Dictionary of performance reports
        """
        report = {}

        for category in self.metrics:
            if not self.metrics[category]:
                continue

            # Get overall average
            overall_avg = self.get_average_duration(category)

            # Get averages by drawing type
            drawing_types = set(m["drawing_type"] for m in self.metrics[category])
            type_averages = {
                dt: self.get_average_duration(category, dt) for dt in drawing_types
            }

            # Get slowest operations
            slowest = self.get_slowest_operations(category, 5)

            report[category] = {
                "overall_average": overall_avg,
                "by_drawing_type": type_averages,
                "slowest_operations": slowest,
                "total_operations": len(self.metrics[category]),
            }

        # Add API statistics
        api_stats = self.get_api_stats()
        if api_stats["count"] > 0:
            report["api_statistics"] = api_stats

            # Calculate percentage of time spent in API calls
            total_processing_time = (
                sum(m["duration"] for m in self.metrics["total_processing"])
                if "total_processing" in self.metrics
                and self.metrics["total_processing"]
                else 0
            )
            if total_processing_time > 0:
                api_percentage = (api_stats["total_time"] / total_processing_time) * 100
                report["api_percentage"] = api_percentage

        # Add token statistics for API calls
        try:
            api_req = self.metrics.get("api_request", [])
            token_records = [m for m in api_req if "completion_tokens" in m and m["completion_tokens"] is not None]
            
            if token_records:
                completion_tokens_list = [m.get("completion_tokens", 0) for m in token_records]
                tps_list = [
                    (m.get("completion_tokens", 0) / m["duration"]) if m["duration"] > 0 else 0
                    for m in token_records
                ]
                
                total_comp = sum(completion_tokens_list)
                avg_comp = total_comp / len(token_records)
                avg_tps = sum(tps_list) / len(tps_list) if tps_list else 0
                
                # Calculate percentiles
                sorted_comp = sorted(completion_tokens_list)
                sorted_tps = sorted(tps_list)
                
                def percentile(data, p):
                    """Calculate percentile from sorted data"""
                    if not data:
                        return 0
                    k = (len(data) - 1) * p
                    f = int(k)
                    c = k - f
                    if f + 1 < len(data):
                        return data[f] + c * (data[f + 1] - data[f])
                    return data[f]
                
                report["api_token_statistics"] = {
                    "samples": len(token_records),
                    "total_completion_tokens": total_comp,
                    "avg_completion_tokens": avg_comp,
                    "avg_tokens_per_second": avg_tps,
                    "completion_tokens_percentiles": {
                        "p50": percentile(sorted_comp, 0.50),
                        "p95": percentile(sorted_comp, 0.95),
                        "p99": percentile(sorted_comp, 0.99),
                    },
                    "tokens_per_second_percentiles": {
                        "p50": percentile(sorted_tps, 0.50),
                        "p95": percentile(sorted_tps, 0.95),
                        "p99": percentile(sorted_tps, 0.99),
                    },
                }
                
                # Per-model breakdown
                models = set(m.get("model") for m in token_records if m.get("model"))
                if models:
                    per_model_stats = {}
                    for model in models:
                        model_records = [m for m in token_records if m.get("model") == model]
                        model_comp = [m.get("completion_tokens", 0) for m in model_records]
                        model_tps = [
                            (m.get("completion_tokens", 0) / m["duration"]) if m["duration"] > 0 else 0
                            for m in model_records
                        ]
                        
                        per_model_stats[model] = {
                            "samples": len(model_records),
                            "avg_completion_tokens": sum(model_comp) / len(model_comp) if model_comp else 0,
                            "avg_tokens_per_second": sum(model_tps) / len(model_tps) if model_tps else 0,
                            "total_completion_tokens": sum(model_comp),
                        }
                    
                    report["api_token_statistics"]["per_model"] = per_model_stats
                    
        except Exception as e:
            self.logger.debug(f"Token stats aggregation error: {str(e)}")

        cost_analysis, file_costs = self._calculate_cost_analysis()
        report["cost_analysis"] = cost_analysis

        ocr_log = self._build_ocr_decision_log(file_costs)
        report["ocr_decision_log"] = ocr_log

        scaling = self._build_scaling_projections(cost_analysis)
        report["scaling_projections"] = scaling

        drawing_costs = self._build_drawing_type_costs(file_costs, ocr_log)
        report["drawing_type_costs"] = drawing_costs

        baseline = self._build_baseline_comparison(scaling, ocr_log, drawing_costs)
        report["baseline_comparison"] = baseline

        return report

    def log_report(self):
        """
        Enhanced log report method that adds API statistics.
        """
        report = self.report()

        self.logger.info("=== Performance Report ===")

        skip_categories = {
            "api_statistics",
            "api_percentage",
            "api_token_statistics",
            "timestamp",
            "formatted_time",
            "cost_analysis",
            "ocr_decision_log",
            "scaling_projections",
            "baseline_comparison",
            "drawing_type_costs",
        }

        for category, data in report.items():
            # Skip special report sections (not operation categories)
            if category in skip_categories:
                continue

            self.logger.info(f"Category: {category}")
            self.logger.info(f"  Overall average: {data['overall_average']:.2f}s")
            self.logger.info(f"  Total operations: {data['total_operations']}")

            self.logger.info("  By drawing type:")
            for dt, avg in data["by_drawing_type"].items():
                self.logger.info(f"    {dt}: {avg:.2f}s")

            self.logger.info("  Slowest operations:")
            for op in data["slowest_operations"]:
                self.logger.info(
                    f"    {op['file_name']} ({op['drawing_type']}): {op['duration']:.2f}s"
                )

        # Log API statistics if available
        if "api_statistics" in report:
            api_stats = report["api_statistics"]
            self.logger.info("=== API Request Statistics ===")
            self.logger.info(f"  Requests: {api_stats['count']}")
            self.logger.info(f"  Min time: {api_stats['min_time']:.2f}s")
            self.logger.info(f"  Max time: {api_stats['max_time']:.2f}s")
            self.logger.info(f"  Avg time: {api_stats['avg_time']:.2f}s")
            self.logger.info(f"  Total time: {api_stats['total_time']:.2f}s")

            if "api_percentage" in report:
                self.logger.info(
                    f"  Percentage of total time: {report['api_percentage']:.2f}%"
                )

        # Log API token statistics (condensed for log file, full details in JSON)
        if "api_token_statistics" in report:
            tstats = report["api_token_statistics"]
            self.logger.info("=== API Token Statistics ===")
            self.logger.info(f"  Samples: {tstats['samples']}, Total tokens: {tstats['total_completion_tokens']:,}")
            self.logger.info(f"  Avg: {tstats['avg_completion_tokens']:.0f} tokens/call, {tstats['avg_tokens_per_second']:.1f} tokens/sec")
            
            # Only log percentiles if DEBUG level (full details always in metrics JSON)
            if self.logger.isEnabledFor(logging.DEBUG):
                # Log percentiles
                if "completion_tokens_percentiles" in tstats:
                    cp = tstats["completion_tokens_percentiles"]
                    self.logger.debug(f"  Completion tokens percentiles - p50: {cp['p50']:.0f}, p95: {cp['p95']:.0f}, p99: {cp['p99']:.0f}")
                
                if "tokens_per_second_percentiles" in tstats:
                    tp = tstats["tokens_per_second_percentiles"]
                    self.logger.debug(f"  Tokens/sec percentiles - p50: {tp['p50']:.2f}, p95: {tp['p95']:.2f}, p99: {tp['p99']:.2f}")
                
                # Log per-model breakdown
                if "per_model" in tstats:
                    self.logger.debug("  Per-model breakdown:")
                    for model, stats in tstats["per_model"].items():
                        self.logger.debug(
                            f"    {model}: {stats['samples']} calls, "
                            f"{stats['avg_completion_tokens']:.0f} avg tokens, "
                            f"{stats['avg_tokens_per_second']:.2f} tokens/sec"
                        )
            else:
                # Condensed summary at INFO level
                self.logger.info(f"  💡 Full token details & percentiles → metrics JSON file")

        self.logger.info("==========================")

    def save_metrics(self, output_path: str) -> bool:
        """
        Save performance metrics to a JSON file.

        Args:
            output_path: Path to save metrics

        Returns:
            bool: True if save was successful, False otherwise
        """
        try:
            # Generate timestamp for filename
            timestamp = time.strftime("%Y%m%d_%H%M%S")

            # Create metrics filename
            metrics_filename = f"metrics_{timestamp}.json"

            # Join the output folder with the metrics filename
            metrics_filepath = os.path.join(output_path, metrics_filename)

            # Create directory if it doesn't exist
            os.makedirs(output_path, exist_ok=True)

            report = self.report()

            # Include timestamp in the metrics data
            report["timestamp"] = time.time()
            report["formatted_time"] = time.strftime("%Y-%m-%d %H:%M:%S")

            # Write to the properly constructed filepath
            with open(metrics_filepath, "w") as f:
                json.dump(report, f, indent=2)

            self.logger.info(f"Saved performance metrics to {metrics_filepath}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save performance metrics: {str(e)}")
            return False

    def load_metrics(self, input_path: str) -> Dict[str, Any]:
        """
        Load performance metrics from a JSON file.

        Args:
            input_path: Path to load metrics from

        Returns:
            Dictionary of metrics or empty dict if file not found
        """
        try:
            if not os.path.exists(input_path):
                return {}

            with open(input_path, "r") as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load performance metrics: {str(e)}")
            return {}

    def compare_metrics(self, previous_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare current metrics with previous metrics.

        Args:
            previous_metrics: Previous metrics to compare with

        Returns:
            Comparison report
        """
        current = self.report()
        comparison = {"timestamp": time.time()}

        # Compare API metrics
        if "api_statistics" in current and "api_statistics" in previous_metrics:
            api_current = current["api_statistics"]
            api_prev = previous_metrics["api_statistics"]

            comparison["api_comparison"] = {
                "avg_time_diff": api_current["avg_time"] - api_prev["avg_time"],
                "avg_time_percent": (
                    (api_current["avg_time"] / api_prev["avg_time"]) - 1
                )
                * 100
                if api_prev["avg_time"] > 0
                else 0,
                "current_avg": api_current["avg_time"],
                "previous_avg": api_prev["avg_time"],
            }

        # Compare category averages
        comparison["category_comparison"] = {}

        for category in current:
            if category in [
                "api_statistics",
                "api_percentage",
                "timestamp",
                "formatted_time",
                "cost_analysis",
                "ocr_decision_log",
                "scaling_projections",
                "baseline_comparison",
                "drawing_type_costs",
            ]:
                continue

            if category in previous_metrics:
                curr_avg = current[category]["overall_average"]
                prev_avg = previous_metrics[category]["overall_average"]

                comparison["category_comparison"][category] = {
                    "avg_diff": curr_avg - prev_avg,
                    "avg_percent": ((curr_avg / prev_avg) - 1) * 100
                    if prev_avg > 0
                    else 0,
                    "current_avg": curr_avg,
                    "previous_avg": prev_avg,
                }

        return comparison

    def record_api_timing_history(self):
        """
        Add current API stats to history for trend analysis.
        """
        if not hasattr(self, "api_timing_history"):
            self.api_timing_history = []

        api_stats = self.get_api_stats()
        if api_stats["count"] > 0:
            self.api_timing_history.append(
                {
                    "timestamp": time.time(),
                    "formatted_time": time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime()
                    ),
                    "avg_time": api_stats["avg_time"],
                    "min_time": api_stats["min_time"],
                    "max_time": api_stats["max_time"],
                    "count": api_stats["count"],
                }
            )
        return self.api_timing_history

    def detect_api_slowdown(
        self, threshold_percent: float = 50.0, min_history_points: int = 1
    ) -> Optional[Dict[str, Any]]:
        """
        Detect significant API slowdown compared to historical average.

        Args:
            threshold_percent: Percentage increase that triggers an alert
            min_history_points: Minimum number of historical data points required

        Returns:
            Alert details if slowdown detected, None otherwise
        """
        # Record current timing in history first
        self.record_api_timing_history()

        if (
            not hasattr(self, "api_timing_history")
            or len(self.api_timing_history) < min_history_points + 1
        ):
            return None

        # Get current stats (most recent entry)
        current_stats = self.api_timing_history[-1]

        # Calculate historical average (excluding most recent)
        historical = self.api_timing_history[:-1]
        if not historical:
            return None

        # Only use the last min_history_points for comparison if we have more
        if len(historical) > min_history_points:
            historical = historical[-min_history_points:]

        historical_avg = sum(entry["avg_time"] for entry in historical) / len(
            historical
        )
        current_avg = current_stats["avg_time"]

        # Calculate percentage increase
        if historical_avg > 0:
            percent_increase = ((current_avg - historical_avg) / historical_avg) * 100

            if percent_increase > threshold_percent:
                return {
                    "alert": "API Slowdown Detected",
                    "current_avg": current_avg,
                    "historical_avg": historical_avg,
                    "percent_increase": percent_increase,
                    "timestamp": time.time(),
                    "formatted_time": time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime()
                    ),
                }

        return None

    def save_metrics_v2(self, output_folder, run_id=None):
        """
        Save performance metrics to a file.
        Also records API timing for historical comparison.

        Args:
            output_folder: Folder to store metrics file
            run_id: Optional run ID to use in filename

        Returns:
            Path to saved metrics file or None if save failed
        """
        # Get full report
        report = self.report()

        # Add timestamp
        report["timestamp"] = time.time()
        report["formatted_time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        # Add API timing history if available
        if hasattr(self, "api_timing_history") and self.api_timing_history:
            report["api_timing_history"] = self.api_timing_history

        # Save to file
        metrics_folder = os.path.join(output_folder, "metrics")
        os.makedirs(metrics_folder, exist_ok=True)

        if run_id is None:
            run_id = time.strftime('%Y%m%d_%H%M%S')
        filename = f"metrics_{run_id}.json"
        metrics_file = os.path.join(metrics_folder, filename)

        try:
            # Import the DateTimeEncoder to handle date objects
            from utils.json_utils import DateTimeEncoder

            with open(metrics_file, "w") as f:
                json.dump(report, f, indent=2, cls=DateTimeEncoder)

            self.logger.info(f"Saved performance metrics to {metrics_file}")

            # Compare with previous metrics if available
            self._log_performance_comparison(metrics_folder)

            return metrics_file
        except Exception as e:
            self.logger.error(f"Failed to save metrics: {str(e)}")
            return None

    def _log_performance_comparison(self, metrics_folder):
        """
        Compare current performance with the most recent previous run.
        Logs changes in performance metrics.

        Args:
            metrics_folder: Folder containing metrics files
        """
        try:
            # Get list of metrics files sorted by modification time (newest first)
            metrics_files = sorted(
                [
                    os.path.join(metrics_folder, f)
                    for f in os.listdir(metrics_folder)
                    if f.startswith("metrics_") and f.endswith(".json")
                ],
                key=os.path.getmtime,
                reverse=True,
            )

            # Need at least two files to compare
            if len(metrics_files) < 2:
                return

            # Current run is the newest file
            current_file = metrics_files[0]
            previous_file = metrics_files[1]

            # Load metrics
            try:
                with open(current_file, "r") as f:
                    current_metrics = json.load(f)

                with open(previous_file, "r") as f:
                    previous_metrics = json.load(f)
            except Exception as e:
                self.logger.warning(
                    f"Could not load metrics files for comparison: {str(e)}"
                )
                return

            # Compare key metrics
            self.logger.info("Performance comparison with previous run:")

            for category in [
                "extraction",
                "ai_processing",
                "api_request",
                "json_parsing",
                "normalization",
                "queue_waiting",
                "extraction_pdf_read",
                "total_processing",
            ]:
                if category in current_metrics and category in previous_metrics:
                    current_avg = current_metrics[category]["overall_average"]
                    previous_avg = previous_metrics[category]["overall_average"]

                    if previous_avg > 0:
                        percent_change = (
                            (current_avg - previous_avg) / previous_avg
                        ) * 100
                        faster_slower = "slower" if percent_change > 0 else "faster"
                        self.logger.info(
                            f"  {category}: {abs(percent_change):.1f}% {faster_slower}"
                        )

            # Compare API stats
            if (
                "api_statistics" in current_metrics
                and "api_statistics" in previous_metrics
            ):
                current_avg = current_metrics["api_statistics"]["avg_time"]
                previous_avg = previous_metrics["api_statistics"]["avg_time"]

                if previous_avg > 0:
                    percent_change = ((current_avg - previous_avg) / previous_avg) * 100
                    faster_slower = "slower" if percent_change > 0 else "faster"
                    self.logger.info(
                        f"  API calls: {abs(percent_change):.1f}% {faster_slower}"
                    )

        except Exception as e:
            self.logger.warning(f"Error during performance comparison: {str(e)}")


# Create a global instance
tracker = PerformanceTracker()


def time_operation(category: str):
    """
    Decorator to time an operation and add it to the tracker.
    
    Automatically extracts file path and drawing type from function arguments,
    checking both positional and keyword arguments.
    
    Args:
        category: Category name for the metric (e.g., 'extraction', 'ai_processing')
    
    Returns:
        Decorated function that tracks execution time
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Find file path in arguments (positional or keyword)
            file_path = None
            drawing_type = None
            
            # Step 1: Check if self (first arg) has a pdf_path attribute
            if args and hasattr(args[0], 'pdf_path'):
                candidate = getattr(args[0], 'pdf_path', None)
                if isinstance(candidate, str) and candidate.lower().endswith('.pdf'):
                    file_path = candidate
            
            # Step 2: Check positional arguments for PDF paths
            if not file_path:
                for arg in args:
                    if isinstance(arg, str) and arg.lower().endswith('.pdf'):
                        file_path = arg
                        break
            
            # Step 3: Check keyword arguments for common file path parameter names
            if not file_path:
                # Check multiple possible parameter names
                for param_name in ['pdf_path', 'file_path', 'filepath', 'path']:
                    kw_file_path = kwargs.get(param_name)
                    if isinstance(kw_file_path, str) and kw_file_path.lower().endswith('.pdf'):
                        file_path = kw_file_path
                        break
            
            # Step 4: If we found a file path, derive the drawing type
            if file_path:
                # Import inside function to avoid circular dependencies
                from utils.drawing_utils import detect_drawing_info
                detected_type, _ = detect_drawing_info(file_path)
                drawing_type = detected_type

            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                
                # Use add_metric_with_context for flexibility
                # It handles None values gracefully and derives file_name internally
                tracker.add_metric_with_context(
                    category=category,
                    duration=duration,
                    file_path=file_path,  # Can be None
                    drawing_type=drawing_type,  # Can be None
                    # Optional: Add debug info when file_path not found
                    **({'func_name': func.__name__} if not file_path else {})
                )

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Find file path in arguments (positional or keyword)
            file_path = None
            drawing_type = None
            
            # Step 1: Check if self (first arg) has a pdf_path attribute
            if args and hasattr(args[0], 'pdf_path'):
                candidate = getattr(args[0], 'pdf_path', None)
                if isinstance(candidate, str) and candidate.lower().endswith('.pdf'):
                    file_path = candidate
            
            # Step 2: Check positional arguments for PDF paths
            if not file_path:
                for arg in args:
                    if isinstance(arg, str) and arg.lower().endswith('.pdf'):
                        file_path = arg
                        break
            
            # Step 3: Check keyword arguments for common file path parameter names
            if not file_path:
                # Check multiple possible parameter names
                for param_name in ['pdf_path', 'file_path', 'filepath', 'path']:
                    kw_file_path = kwargs.get(param_name)
                    if isinstance(kw_file_path, str) and kw_file_path.lower().endswith('.pdf'):
                        file_path = kw_file_path
                        break
            
            # Step 4: If we found a file path, derive the drawing type
            if file_path:
                # Import inside function to avoid circular dependencies
                from utils.drawing_utils import detect_drawing_info
                detected_type, _ = detect_drawing_info(file_path)
                drawing_type = detected_type

            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                
                # Use add_metric_with_context for flexibility
                # It handles None values gracefully and derives file_name internally
                tracker.add_metric_with_context(
                    category=category,
                    duration=duration,
                    file_path=file_path,  # Can be None
                    drawing_type=drawing_type,  # Can be None
                    # Optional: Add debug info when file_path not found
                    **({'func_name': func.__name__} if not file_path else {})
                )

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


@contextmanager
def time_operation_context(category: str, file_path: Optional[str] = None, drawing_type: Optional[str] = None):
    """
    Context manager for timing operations with explicit context.

    Args:
        category: Category of the operation
        file_path: Optional path to the file being processed
        drawing_type: Optional type of drawing
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        tracker = get_tracker()
        # Use add_metric_with_context which handles None defaults
        tracker.add_metric_with_context(
            category=category,
            duration=duration,
            file_path=file_path,
            drawing_type=drawing_type
        )


# Get the global tracker
def get_tracker() -> PerformanceTracker:
    """
    Get the global performance tracker.

    Returns:
        Global PerformanceTracker instance
    """
    return tracker
