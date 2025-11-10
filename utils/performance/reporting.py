"""
Reporting and logging utilities for performance metrics.
"""
import logging
from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from utils.performance.tracker import PerformanceTracker


def log_report(tracker: "PerformanceTracker", report: Dict[str, Any]):
    """
    Enhanced log report method that adds API statistics.
    
    Args:
        tracker: PerformanceTracker instance
        report: Report dictionary from tracker.report()
    """
    logger = tracker.logger
    
    logger.info("=== Performance Report ===")

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

        logger.info(f"Category: {category}")
        logger.info(f"  Overall average: {data['overall_average']:.2f}s")
        logger.info(f"  Total operations: {data['total_operations']}")

        logger.info("  By drawing type:")
        for dt, avg in data["by_drawing_type"].items():
            logger.info(f"    {dt}: {avg:.2f}s")

        logger.info("  Slowest operations:")
        for op in data["slowest_operations"]:
            logger.info(
                f"    {op['file_name']} ({op['drawing_type']}): {op['duration']:.2f}s"
            )

    # Log API statistics if available
    if "api_statistics" in report:
        api_stats = report["api_statistics"]
        logger.info("=== API Request Statistics ===")
        logger.info(f"  Requests: {api_stats['count']}")
        logger.info(f"  Min time: {api_stats['min_time']:.2f}s")
        logger.info(f"  Max time: {api_stats['max_time']:.2f}s")
        logger.info(f"  Avg time: {api_stats['avg_time']:.2f}s")
        logger.info(f"  Total time: {api_stats['total_time']:.2f}s")

        if "api_percentage" in report:
            logger.info(
                f"  Percentage of total time: {report['api_percentage']:.2f}%"
            )

    # Log API token statistics (condensed for log file, full details in JSON)
    if "api_token_statistics" in report:
        tstats = report["api_token_statistics"]
        logger.info("=== API Token Statistics ===")
        logger.info(f"  Samples: {tstats['samples']}, Total tokens: {tstats['total_completion_tokens']:,}")
        logger.info(f"  Avg: {tstats['avg_completion_tokens']:.0f} tokens/call, {tstats['avg_tokens_per_second']:.1f} tokens/sec")
        
        # Only log percentiles if DEBUG level (full details always in metrics JSON)
        if logger.isEnabledFor(logging.DEBUG):
            # Log percentiles
            if "completion_tokens_percentiles" in tstats:
                cp = tstats["completion_tokens_percentiles"]
                logger.debug(f"  Completion tokens percentiles - p50: {cp['p50']:.0f}, p95: {cp['p95']:.0f}, p99: {cp['p99']:.0f}")
            
            if "tokens_per_second_percentiles" in tstats:
                tp = tstats["tokens_per_second_percentiles"]
                logger.debug(f"  Tokens/sec percentiles - p50: {tp['p50']:.2f}, p95: {tp['p95']:.2f}, p99: {tp['p99']:.2f}")
            
            # Log per-model breakdown
            if "per_model" in tstats:
                logger.debug("  Per-model breakdown:")
                for model, stats in tstats["per_model"].items():
                    logger.debug(
                        f"    {model}: {stats['samples']} calls, "
                        f"{stats['avg_completion_tokens']:.0f} avg tokens, "
                        f"{stats['avg_tokens_per_second']:.2f} tokens/sec"
                    )
        else:
            # Condensed summary at INFO level
            logger.info(f"  💡 Full token details & percentiles → metrics JSON file")

    logger.info("==========================")

