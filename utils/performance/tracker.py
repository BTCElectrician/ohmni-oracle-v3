"""
Core PerformanceTracker class for collecting and managing metrics.
"""
import os
import logging
from typing import Dict, Any, List, Optional
import time

from utils.performance.aggregations import (
    calculate_cost_analysis,
    build_ocr_decision_log,
    build_drawing_type_costs,
    build_scaling_projections,
    build_baseline_comparison,
    calculate_token_statistics,
)
from utils.performance.reporting import log_report
from utils.performance.persistence import (
    save_metrics as _save_metrics,
    load_metrics as _load_metrics,
    compare_metrics as _compare_metrics,
    save_metrics_v2 as _save_metrics_v2,
    log_performance_comparison as _log_performance_comparison,
)


class PerformanceTracker:
    """
    Tracks performance metrics for different operations.
    """

    def __init__(self):
        # Add new categories for tracking
        self.metrics = {
            "extraction": [],
            "ai_processing": [],
            "api_request": [],
            "json_parsing": [],
            "normalization": [],
            "queue_waiting": [],
            "extraction_pdf_read": [],
            "total_processing": [],
            "ocr_processing": [],
            "ocr_decision": [],
            "api_cache_hit": [],
        }

        # Add metrics for tracking API variability
        self.api_stats = {
            "min_time": float("inf"),
            "max_time": 0,
            "total_time": 0,
            "count": 0,
        }

        # Store actual wall-clock elapsed time (not cumulative worker time)
        self.actual_elapsed_time = None

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

    def set_actual_elapsed_time(self, elapsed_seconds: float):
        """
        Set the actual wall-clock elapsed time for the entire run.

        This is different from summing individual file processing times,
        especially when files are processed in parallel.

        Args:
            elapsed_seconds: Total wall-clock time in seconds from start to finish
        """
        self.actual_elapsed_time = elapsed_seconds

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
            token_stats = calculate_token_statistics(self.metrics.get("api_request", []))
            if token_stats:
                report["api_token_statistics"] = token_stats
        except Exception as e:
            self.logger.debug(f"Token stats aggregation error: {str(e)}")

        cost_analysis, file_costs = calculate_cost_analysis(self.metrics)
        report["cost_analysis"] = cost_analysis

        ocr_log = build_ocr_decision_log(self.metrics, file_costs)
        report["ocr_decision_log"] = ocr_log

        scaling = build_scaling_projections(self.metrics, cost_analysis, self.actual_elapsed_time)
        report["scaling_projections"] = scaling

        drawing_costs = build_drawing_type_costs(file_costs, ocr_log)
        report["drawing_type_costs"] = drawing_costs

        baseline = build_baseline_comparison(scaling, ocr_log, drawing_costs)
        report["baseline_comparison"] = baseline

        return report

    def log_report(self):
        """
        Enhanced log report method that adds API statistics.
        """
        report = self.report()
        log_report(self, report)

    def record_api_timing_history(self):
        """
        Add current API stats to history for trend analysis.
        """
        if not hasattr(self, "api_timing_history"):
            self.api_timing_history = []

        api_stats = self.get_api_stats()
        if api_stats["count"] > 0:
            import time
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
                import time
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

    def save_metrics(self, output_path: str) -> bool:
        """
        Save performance metrics to a JSON file.

        Args:
            output_path: Path to save metrics

        Returns:
            bool: True if save was successful, False otherwise
        """
        return _save_metrics(self, output_path)

    def load_metrics(self, input_path: str) -> Dict[str, Any]:
        """
        Load performance metrics from a JSON file.

        Args:
            input_path: Path to load metrics from

        Returns:
            Dictionary of metrics or empty dict if file not found
        """
        return _load_metrics(input_path)

    def compare_metrics(self, previous_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare current metrics with previous metrics.

        Args:
            previous_metrics: Previous metrics to compare with

        Returns:
            Comparison report
        """
        return _compare_metrics(self, previous_metrics)

    def save_metrics_v2(self, output_folder: str, run_id: Optional[str] = None) -> Optional[str]:
        """
        Save performance metrics to a file.
        Also records API timing for historical comparison.

        Args:
            output_folder: Folder to store metrics file
            run_id: Optional run ID to use in filename

        Returns:
            Path to saved metrics file or None if save failed
        """
        return _save_metrics_v2(self, output_folder, run_id)

    def _log_performance_comparison(self, metrics_folder: str) -> None:
        """
        Compare current performance with the most recent previous run.
        Logs changes in performance metrics.

        Args:
            metrics_folder: Folder containing metrics files
        """
        _log_performance_comparison(self, metrics_folder)


def get_tracker() -> PerformanceTracker:
    """
    Get the global performance tracker.

    Returns:
        Global PerformanceTracker instance
    """
    from utils.performance import tracker
    return tracker

