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
)
from functools import wraps
from contextlib import contextmanager

T = TypeVar("T")


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

        return report

    def log_report(self):
        """
        Enhanced log report method that adds API statistics.
        """
        report = self.report()

        self.logger.info("=== Performance Report ===")

        for category, data in report.items():
            if category == "api_statistics" or category == "api_percentage":
                continue  # Skip these for now, we'll handle them separately

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
