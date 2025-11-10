"""
Tests for modularized performance tracking components.
"""
import pytest
import os
import tempfile
import json
from utils.performance import (
    PerformanceTracker,
    tracker,
    get_tracker,
    time_operation,
    time_operation_context,
)
from utils.performance.pricing import load_pricing_table, PRICING_TIER_4
from utils.performance.config import (
    TIER4_MONTHLY_LIMIT,
    BASELINE_AVG_TIME,
    METRICS_AVG_CHARS_PER_TOKEN,
)
from utils.performance.aggregations import (
    calculate_cost_analysis,
    normalize_ocr_reason,
    build_ocr_decision_log,
    build_drawing_type_costs,
    build_scaling_projections,
    build_baseline_comparison,
    calculate_token_statistics,
    is_ocr_metric_entry,
)
from utils.performance.persistence import (
    save_metrics,
    load_metrics,
    compare_metrics,
    save_metrics_v2,
    set_writer,
    LocalFileWriter,
)


class TestPricing:
    """Test pricing module."""
    
    def test_load_pricing_table(self):
        """Test that pricing table loads correctly."""
        table = load_pricing_table()
        assert isinstance(table, dict)
        assert "gpt-4.1" in table
        assert "input" in table["gpt-4.1"]
        assert "output" in table["gpt-4.1"]
    
    def test_pricing_tier_4_available(self):
        """Test that PRICING_TIER_4 is available."""
        assert PRICING_TIER_4 is not None
        assert len(PRICING_TIER_4) > 0


class TestAggregations:
    """Test aggregation functions."""
    
    def test_is_ocr_metric_entry(self):
        """Test OCR metric detection."""
        assert is_ocr_metric_entry({"is_ocr": True})
        assert is_ocr_metric_entry({"api_type": "ocr_something"})
        assert is_ocr_metric_entry({"model": "gpt-4o-mini-ocr"})
        assert not is_ocr_metric_entry({"model": "gpt-4.1"})
        assert not is_ocr_metric_entry({})
    
    def test_normalize_ocr_reason(self):
        """Test OCR reason normalization."""
        assert normalize_ocr_reason("force_panel") == "forced_panel_ocr"
        assert normalize_ocr_reason("low density") == "char_density_low"
        assert normalize_ocr_reason("sufficient text") == "sufficient_text"
        assert normalize_ocr_reason(None) == "unknown"
        assert normalize_ocr_reason("") == "unknown"
    
    def test_calculate_cost_analysis(self):
        """Test cost analysis calculation."""
        metrics = {
            "api_request": [
                {
                    "model": "gpt-4.1",
                    "prompt_tokens": 1000,
                    "completion_tokens": 500,
                    "file_name": "test.pdf",
                    "drawing_type": "Architectural",
                }
            ],
            "total_processing": [{"duration": 10.0}],
        }
        cost_analysis, file_costs = calculate_cost_analysis(metrics)
        assert "tier_4_pricing" in cost_analysis
        assert "by_model" in cost_analysis
        assert "cost_summary" in cost_analysis
        assert "test.pdf" in file_costs
    
    def test_calculate_token_statistics(self):
        """Test token statistics calculation."""
        api_metrics = [
            {
                "completion_tokens": 100,
                "duration": 2.0,
                "model": "gpt-4.1",
            },
            {
                "completion_tokens": 200,
                "duration": 3.0,
                "model": "gpt-4.1",
            },
        ]
        stats = calculate_token_statistics(api_metrics)
        assert stats is not None
        assert stats["samples"] == 2
        assert stats["total_completion_tokens"] == 300
        assert "per_model" in stats


class TestDecorators:
    """Test decorator functionality."""
    
    def test_time_operation_sync(self):
        """Test sync function decorator."""
        # Use global tracker
        from utils.performance import tracker
        
        initial_count = len(tracker.metrics.get("test_category", []))
        
        @time_operation("test_category")
        def test_func():
            return "done"
        
        result = test_func()
        assert result == "done"
        assert len(tracker.metrics.get("test_category", [])) > initial_count
    
    def test_time_operation_context(self):
        """Test context manager."""
        # Use global tracker
        from utils.performance import tracker
        
        initial_count = len(tracker.metrics.get("test_context", []))
        
        with time_operation_context("test_context", "test.pdf", "Architectural"):
            pass
        
        metrics = tracker.metrics.get("test_context", [])
        assert len(metrics) > initial_count
        assert metrics[-1]["file_name"] == "test.pdf"


class TestPersistence:
    """Test persistence functionality."""
    
    def test_save_and_load_metrics(self):
        """Test saving and loading metrics."""
        tracker = PerformanceTracker()
        tracker.add_metric("test", "test.pdf", "Architectural", 1.5)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = save_metrics(tracker, tmpdir)
            assert result is True
            
            # Find the saved file
            files = [f for f in os.listdir(tmpdir) if f.startswith("metrics_")]
            assert len(files) > 0
            
            file_path = os.path.join(tmpdir, files[0])
            loaded = load_metrics(file_path)
            assert "test" in loaded
    
    def test_compare_metrics(self):
        """Test metrics comparison."""
        tracker = PerformanceTracker()
        tracker.add_metric("test", "test.pdf", "Architectural", 1.5)
        
        previous = {
            "test": {
                "overall_average": 1.0,
                "by_drawing_type": {},
                "slowest_operations": [],
                "total_operations": 1,
            }
        }
        
        comparison = compare_metrics(tracker, previous)
        assert "category_comparison" in comparison
        assert "test" in comparison["category_comparison"]
    
    def test_custom_writer(self):
        """Test custom writer interface."""
        written_data = {}
        
        class TestWriter:
            def write(self, file_path: str, data: dict) -> bool:
                written_data["path"] = file_path
                written_data["data"] = data
                return True
        
        set_writer(TestWriter())
        
        tracker = PerformanceTracker()
        tracker.add_metric("test", "test.pdf", "Architectural", 1.5)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            save_metrics(tracker, tmpdir)
            assert "path" in written_data
            assert "data" in written_data
        
        # Reset to default
        set_writer(None)


class TestTracker:
    """Test PerformanceTracker class."""
    
    def test_add_metric(self):
        """Test adding metrics."""
        tracker = PerformanceTracker()
        tracker.add_metric("test", "test.pdf", "Architectural", 1.5)
        assert len(tracker.metrics["test"]) == 1
    
    def test_add_api_metric(self):
        """Test adding API metrics."""
        tracker = PerformanceTracker()
        tracker.add_api_metric(2.5)
        tracker.add_api_metric(3.7)
        stats = tracker.get_api_stats()
        assert stats["count"] == 2
        assert stats["min_time"] == 2.5
        assert stats["max_time"] == 3.7
    
    def test_get_average_duration(self):
        """Test getting average duration."""
        tracker = PerformanceTracker()
        tracker.add_metric("test", "test.pdf", "Architectural", 1.0)
        tracker.add_metric("test", "test2.pdf", "Architectural", 3.0)
        avg = tracker.get_average_duration("test")
        assert avg == 2.0
    
    def test_report(self):
        """Test report generation."""
        tracker = PerformanceTracker()
        tracker.add_metric("test", "test.pdf", "Architectural", 1.5)
        report = tracker.report()
        assert "test" in report
        assert "cost_analysis" in report
        assert "ocr_decision_log" in report

