"""
Unit tests for the MVP metrics additions (cost analysis, OCR logs, scaling, etc.).
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from utils.performance_utils import PerformanceTracker


def _find_entry(entries, file_name):
    for entry in entries:
        if entry.get("file_name") == file_name:
            return entry
    raise AssertionError(f"Missing metrics entry for {file_name}")


def test_mvp_metrics_sections_present_and_populated():
    tracker = PerformanceTracker()

    # Simulate total processing for two drawings
    tracker.add_metric("total_processing", "/tmp/file1.pdf", "Electrical", 120.0)
    tracker.add_metric("total_processing", "/tmp/file2.pdf", "Mechanical", 90.0)

    # API usage for file1 (main processing)
    tracker.add_metric_with_context(
        category="api_request",
        duration=5.0,
        file_path="/tmp/file1.pdf",
        drawing_type="Electrical",
        model="gpt-4.1-mini",
        api_type="chat",
        prompt_tokens=1000,
        completion_tokens=2000,
        total_tokens=3000,
    )

    # OCR usage for file1
    tracker.add_metric_with_context(
        category="api_request",
        duration=2.0,
        file_path="/tmp/file1.pdf",
        drawing_type="Electrical",
        model="gpt-4o-mini-ocr",
        api_type="ocr_tile",
        prompt_tokens=500,
        completion_tokens=600,
        total_tokens=1100,
        is_ocr=True,
    )

    # API usage for file2
    tracker.add_metric_with_context(
        category="api_request",
        duration=4.0,
        file_path="/tmp/file2.pdf",
        drawing_type="Mechanical",
        model="gpt-4.1-mini",
        api_type="chat",
        prompt_tokens=2000,
        completion_tokens=1000,
        total_tokens=3000,
    )

    # OCR decision entries for both files
    tracker.add_metric_with_context(
        category="ocr_decision",
        duration=8.0,
        file_path="/tmp/file1.pdf",
        drawing_type="Electrical",
        performed=True,
        reason="char_density_low",
        char_count_total=1800,
        char_count_threshold=1500,
        estimated_tokens=450,
        token_threshold=5000,
        tiles_processed=3,
        ocr_duration_seconds=8.0,
    )
    tracker.add_metric_with_context(
        category="ocr_decision",
        duration=0.0,
        file_path="/tmp/file2.pdf",
        drawing_type="Mechanical",
        performed=False,
        reason="sufficient_text_density",
        char_count_total=6000,
        char_count_threshold=1500,
        estimated_tokens=1500,
        token_threshold=5000,
        tiles_processed=0,
        ocr_duration_seconds=0.0,
    )

    report = tracker.report()

    assert "cost_analysis" in report
    assert "ocr_decision_log" in report
    assert "scaling_projections" in report
    assert "baseline_comparison" in report
    assert "drawing_type_costs" in report

    cost_analysis = report["cost_analysis"]
    by_model = cost_analysis["by_model"]
    assert by_model["gpt-4.1-mini"]["total_input_tokens"] == 3000
    assert by_model["gpt-4o-mini-ocr"]["total_input_tokens"] == 500
    assert cost_analysis["cost_summary"]["grand_total"] > 0

    ocr_log = report["ocr_decision_log"]
    assert ocr_log["summary"]["total_files"] == 2
    file1_entry = _find_entry(ocr_log["by_file"], "file1.pdf")
    file2_entry = _find_entry(ocr_log["by_file"], "file2.pdf")
    assert file1_entry["ocr_triggered"] is True
    assert file1_entry["tiles_processed"] >= 3
    assert file2_entry["ocr_triggered"] is False

    drawing_costs = report["drawing_type_costs"]
    assert drawing_costs["by_type"]["Electrical"]["count"] == 1
    assert drawing_costs["by_type"]["Electrical"]["ocr_trigger_rate"] > 0

    scaling = report["scaling_projections"]
    assert scaling["current_run"]["files_processed"] == 2
    assert scaling["extrapolated"]["files_per_hour"] > 0

    baseline = report["baseline_comparison"]
    assert baseline["baseline"]["avg_time_per_drawing"] > 0
    assert isinstance(baseline["recommendation"], str)
