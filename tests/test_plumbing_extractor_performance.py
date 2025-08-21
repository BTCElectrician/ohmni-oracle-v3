"""
Performance comparison test for PlumbingExtractor vs PyMuPdfExtractor.
"""
import os
import sys
import time
import asyncio
import logging
from tabulate import tabulate
from datetime import datetime
import statistics
import json

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.extraction_service import PlumbingExtractor, PyMuPdfExtractor

# Set up logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test")

# Test file path - update as needed
TEST_FILE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "test_data", "plumbing_fixture_schedule.pdf"
)

# Number of test iterations for more reliable performance measurements
ITERATIONS = 5


async def run_extractor_test(extractor_class, file_path, iterations=1):
    """Run an extractor multiple times and collect performance metrics."""
    instance = extractor_class(logger)
    durations = []

    # Get file info
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path) / 1024  # KB

    # Run extraction multiple times
    for i in range(iterations):
        start_time = time.time()
        result = await instance.extract(file_path)
        end_time = time.time()
        duration = end_time - start_time
        durations.append(duration)

        # Sanity check to ensure extraction actually worked
        if not result.success:
            logger.error(f"Extraction {i+1} failed for {extractor_class.__name__}")
            continue

        # Wait briefly between iterations to allow system resources to stabilize
        await asyncio.sleep(0.1)

    # Calculate statistics
    avg_duration = statistics.mean(durations) if durations else 0
    median_duration = statistics.median(durations) if durations else 0
    min_duration = min(durations) if durations else 0
    max_duration = max(durations) if durations else 0

    return {
        "extractor": extractor_class.__name__,
        "file_name": file_name,
        "file_size_kb": file_size,
        "iterations": len(durations),
        "avg_duration": avg_duration,
        "median_duration": median_duration,
        "min_duration": min_duration,
        "max_duration": max_duration,
        "raw_durations": durations,
    }


async def compare_extractors(file_path, iterations=5):
    """Compare the performance of PlumbingExtractor vs PyMuPdfExtractor."""
    logger.info(f"Starting performance comparison on {os.path.basename(file_path)}")
    logger.info(f"Running {iterations} iterations per extractor...")

    # Run tests for each extractor
    base_results = await run_extractor_test(PyMuPdfExtractor, file_path, iterations)
    plumbing_results = await run_extractor_test(
        PlumbingExtractor, file_path, iterations
    )

    # Calculate improvement
    base_avg = base_results["avg_duration"]
    plumbing_avg = plumbing_results["avg_duration"]

    if base_avg > 0:
        percent_diff = ((plumbing_avg - base_avg) / base_avg) * 100
    else:
        percent_diff = 0

    # Prepare comparison table
    comparison = [
        ["Extractor", "Avg Duration (s)", "Median (s)", "Min (s)", "Max (s)"],
        [
            base_results["extractor"],
            f"{base_avg:.4f}",
            f"{base_results['median_duration']:.4f}",
            f"{base_results['min_duration']:.4f}",
            f"{base_results['max_duration']:.4f}",
        ],
        [
            plumbing_results["extractor"],
            f"{plumbing_avg:.4f}",
            f"{plumbing_results['median_duration']:.4f}",
            f"{plumbing_results['min_duration']:.4f}",
            f"{plumbing_results['max_duration']:.4f}",
        ],
        [
            "Difference",
            f"{plumbing_avg - base_avg:.4f}",
            f"{plumbing_results['median_duration'] - base_results['median_duration']:.4f}",
            f"{plumbing_results['min_duration'] - base_results['min_duration']:.4f}",
            f"{plumbing_results['max_duration'] - base_results['max_duration']:.4f}",
        ],
        ["% Change", f"{percent_diff:.2f}%", "", "", ""],
    ]

    # Print the comparison table
    logger.info("\nPerformance Comparison Results:")
    logger.info(
        f"File: {base_results['file_name']} ({base_results['file_size_kb']:.2f} KB)"
    )
    logger.info(tabulate(comparison, headers="firstrow"))

    # Output interpretation
    if percent_diff > 5:
        logger.info(
            "\nNote: The specialized PlumbingExtractor is slower than the base extractor."
        )
        logger.info(
            "This is expected due to the additional processing for content enhancement and table prioritization."
        )
        logger.info(
            "The performance trade-off may be acceptable if it significantly improves extraction quality."
        )
    elif percent_diff < -5:
        logger.info(
            "\nNote: The specialized PlumbingExtractor is faster than the base extractor."
        )
        logger.info(
            "This is an unexpected but positive result. Further analysis may be warranted."
        )
    else:
        logger.info("\nNote: The performance difference is minimal (within 5%).")
        logger.info(
            "The specialized extractor adds value without significant performance impact."
        )

    # Save the detailed results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(os.path.dirname(__file__), "..", "output_test")
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, f"performance_comparison_{timestamp}.json")
    with open(output_file, "w") as f:
        json.dump(
            {
                "base_extractor": base_results,
                "plumbing_extractor": plumbing_results,
                "comparison": {
                    "absolute_diff": plumbing_avg - base_avg,
                    "percent_diff": percent_diff,
                    "file_path": file_path,
                    "timestamp": timestamp,
                },
            },
            f,
            indent=2,
        )

    logger.info(f"Detailed results saved to: {output_file}")

    # Return the results
    return {
        "base_extractor": base_results,
        "plumbing_extractor": plumbing_results,
        "percent_diff": percent_diff,
    }


async def main():
    """Main entry point for the performance test script."""
    if not os.path.exists(TEST_FILE_PATH):
        logger.error(f"Test file not found: {TEST_FILE_PATH}")
        logger.info(
            "Please update the TEST_FILE_PATH variable with a valid plumbing PDF file."
        )
        return

    try:
        await compare_extractors(TEST_FILE_PATH, iterations=ITERATIONS)
    except Exception as e:
        logger.error(f"Error running performance comparison: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
