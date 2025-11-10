"""
Persistence utilities for saving and loading performance metrics.
"""
import os
import json
import time
from typing import Dict, Any, Optional, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from utils.performance.tracker import PerformanceTracker


class MetricsWriter(Protocol):
    """
    Protocol for pluggable metrics writers (e.g., blob storage).
    
    Implement this protocol to add custom storage backends.
    """
    def write(self, file_path: str, data: Dict[str, Any]) -> bool:
        """
        Write metrics data to storage.
        
        Args:
            file_path: Path where data should be written
            data: Metrics data dictionary
            
        Returns:
            True if write succeeded, False otherwise
        """
        ...


class LocalFileWriter:
    """Default local file writer implementation."""
    
    def write(self, file_path: str, data: Dict[str, Any]) -> bool:
        """Write to local filesystem."""
        try:
            dir_path = os.path.dirname(file_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            return False


# Module-level writer instance (can be replaced for custom storage)
_writer: Optional[MetricsWriter] = None


def set_writer(writer: Optional[MetricsWriter]) -> None:
    """
    Set a custom metrics writer (e.g., for blob storage).
    
    Args:
        writer: Writer instance implementing MetricsWriter protocol, or None to use default
    """
    global _writer
    _writer = writer


def get_writer() -> MetricsWriter:
    """Get the current metrics writer (defaults to LocalFileWriter)."""
    global _writer
    if _writer is None:
        _writer = LocalFileWriter()
    return _writer


def save_metrics(tracker: "PerformanceTracker", output_path: str) -> bool:
    """
    Save performance metrics to a JSON file.

    Args:
        tracker: PerformanceTracker instance
        output_path: Path to save metrics

    Returns:
        bool: True if save was successful, False otherwise
    """
    try:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        metrics_filename = f"metrics_{timestamp}.json"
        metrics_filepath = os.path.join(output_path, metrics_filename)

        report = tracker.report()
        report["timestamp"] = time.time()
        report["formatted_time"] = time.strftime("%Y-%m-%d %H:%M:%S")

        writer = get_writer()
        if writer.write(metrics_filepath, report):
            tracker.logger.info(f"Saved performance metrics to {metrics_filepath}")
            return True
        else:
            tracker.logger.error(f"Failed to write metrics to {metrics_filepath}")
            return False
    except Exception as e:
        tracker.logger.error(f"Failed to save performance metrics: {str(e)}")
        return False


def load_metrics(input_path: str) -> Dict[str, Any]:
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
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to load performance metrics: {str(e)}")
        return {}


def compare_metrics(tracker: "PerformanceTracker", previous_metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare current metrics with previous metrics.

    Args:
        tracker: PerformanceTracker instance
        previous_metrics: Previous metrics to compare with

    Returns:
        Comparison report
    """
    current = tracker.report()
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

    skip_keys = {
        "api_statistics",
        "api_percentage",
        "timestamp",
        "formatted_time",
        "cost_analysis",
        "ocr_decision_log",
        "scaling_projections",
        "baseline_comparison",
        "drawing_type_costs",
    }

    for category in current:
        if category in skip_keys:
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


def save_metrics_v2(tracker: "PerformanceTracker", output_folder: str, run_id: Optional[str] = None) -> Optional[str]:
    """
    Save performance metrics to a file.
    Also records API timing for historical comparison.

    Args:
        tracker: PerformanceTracker instance
        output_folder: Folder to store metrics file
        run_id: Optional run ID to use in filename

    Returns:
        Path to saved metrics file or None if save failed
    """
    report = tracker.report()
    report["timestamp"] = time.time()
    report["formatted_time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    # Add API timing history if available
    if hasattr(tracker, "api_timing_history") and tracker.api_timing_history:
        report["api_timing_history"] = tracker.api_timing_history

    metrics_folder = os.path.join(output_folder, "metrics")
    os.makedirs(metrics_folder, exist_ok=True)

    if run_id is None:
        run_id = time.strftime('%Y%m%d_%H%M%S')
    filename = f"metrics_{run_id}.json"
    metrics_file = os.path.join(metrics_folder, filename)

    try:
        from utils.json_utils import DateTimeEncoder
        
        # Use DateTimeEncoder for JSON serialization
        class DateTimeEncoderWriter:
            def write(self, file_path: str, data: Dict[str, Any]) -> bool:
                try:
                    dir_path = os.path.dirname(file_path)
                    if dir_path:
                        os.makedirs(dir_path, exist_ok=True)
                    with open(file_path, "w") as f:
                        json.dump(data, f, indent=2, cls=DateTimeEncoder)
                    return True
                except Exception:
                    return False
        
        writer = DateTimeEncoderWriter()
        if writer.write(metrics_file, report):
            tracker.logger.info(f"Saved performance metrics to {metrics_file}")
            log_performance_comparison(tracker, metrics_folder)
            return metrics_file
        else:
            tracker.logger.error(f"Failed to write metrics to {metrics_file}")
            return None
    except Exception as e:
        tracker.logger.error(f"Failed to save metrics: {str(e)}")
        return None


def log_performance_comparison(tracker: "PerformanceTracker", metrics_folder: str) -> None:
    """
    Compare current performance with the most recent previous run.
    Logs changes in performance metrics.

    Args:
        tracker: PerformanceTracker instance
        metrics_folder: Folder containing metrics files
    """
    try:
        metrics_files = sorted(
            [
                os.path.join(metrics_folder, f)
                for f in os.listdir(metrics_folder)
                if f.startswith("metrics_") and f.endswith(".json")
            ],
            key=os.path.getmtime,
            reverse=True,
        )

        if len(metrics_files) < 2:
            return

        current_file = metrics_files[0]
        previous_file = metrics_files[1]

        try:
            with open(current_file, "r") as f:
                current_metrics = json.load(f)

            with open(previous_file, "r") as f:
                previous_metrics = json.load(f)
        except Exception as e:
            tracker.logger.warning(
                f"Could not load metrics files for comparison: {str(e)}"
            )
            return

        tracker.logger.info("Performance comparison with previous run:")

        categories = [
            "extraction",
            "ai_processing",
            "api_request",
            "json_parsing",
            "normalization",
            "queue_waiting",
            "extraction_pdf_read",
            "total_processing",
        ]

        for category in categories:
            if category in current_metrics and category in previous_metrics:
                current_avg = current_metrics[category]["overall_average"]
                previous_avg = previous_metrics[category]["overall_average"]

                if previous_avg > 0:
                    percent_change = (
                        (current_avg - previous_avg) / previous_avg
                    ) * 100
                    faster_slower = "slower" if percent_change > 0 else "faster"
                    tracker.logger.info(
                        f"  {category}: {abs(percent_change):.1f}% {faster_slower}"
                    )

        if (
            "api_statistics" in current_metrics
            and "api_statistics" in previous_metrics
        ):
            current_avg = current_metrics["api_statistics"]["avg_time"]
            previous_avg = previous_metrics["api_statistics"]["avg_time"]

            if previous_avg > 0:
                percent_change = ((current_avg - previous_avg) / previous_avg) * 100
                faster_slower = "slower" if percent_change > 0 else "faster"
                tracker.logger.info(
                    f"  API calls: {abs(percent_change):.1f}% {faster_slower}"
                )

    except Exception as e:
        tracker.logger.warning(f"Error during performance comparison: {str(e)}")

