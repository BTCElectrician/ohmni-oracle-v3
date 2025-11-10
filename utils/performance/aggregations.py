"""
Pure aggregation functions for performance metrics analysis.

All functions follow RORO (Receive an Object, Return an Object) pattern.
"""
from typing import Dict, Any, List, Tuple, Optional

from utils.performance.pricing import PRICING_TIER_4
from utils.performance.config import (
    TIER4_MONTHLY_LIMIT,
    METRICS_AVG_CHARS_PER_TOKEN,
    WORKDAY_HOURS,
    WORKDAYS_PER_MONTH,
    STORAGE_PER_1000_FILES_GB,
    AZURE_STORAGE_COST_PER_GB,
    BASELINE_AVG_TIME,
    BASELINE_DATE,
    BASELINE_ACCEPTABLE_MIN,
    BASELINE_ACCEPTABLE_MAX,
    BASELINE_COST_PER_DRAWING,
)


def is_ocr_metric_entry(metric: Dict[str, Any]) -> bool:
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


def calculate_cost_analysis(metrics: Dict[str, List[Dict[str, Any]]]) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
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
    api_metrics = metrics.get("api_request", [])

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

        if is_ocr_metric_entry(metric):
            file_entry["ocr_cost"] += total_cost
            file_entry["tiles_processed"] += 1
            ocr_total += total_cost
        else:
            file_entry["main_cost"] += total_cost
            main_total += total_cost

    grand_total = main_total + ocr_total
    files_processed = len(metrics.get("total_processing", []))
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


def normalize_ocr_reason(reason: Optional[str]) -> str:
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


def build_ocr_decision_log(
    metrics: Dict[str, List[Dict[str, Any]]], file_costs: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """Summarize OCR trigger decisions per file."""
    ocr_metrics = metrics.get("ocr_decision", [])
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
        trigger_reason = normalize_ocr_reason(reason_detail)

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


def build_drawing_type_costs(
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


def build_scaling_projections(
    metrics: Dict[str, List[Dict[str, Any]]], cost_analysis: Dict[str, Any]
) -> Dict[str, Any]:
    """Project throughput and spend at larger scales."""
    total_processing = metrics.get("total_processing", [])
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


def build_baseline_comparison(
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


def calculate_token_statistics(api_metrics: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Calculate token statistics from API metrics."""
    token_records = [m for m in api_metrics if "completion_tokens" in m and m["completion_tokens"] is not None]
    
    if not token_records:
        return None
    
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
    
    result = {
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
        
        result["per_model"] = per_model_stats
    
    return result

