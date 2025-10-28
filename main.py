import os
import sys
import asyncio
import logging
import time

from openai import AsyncOpenAI
from config.settings import OPENAI_API_KEY, get_all_settings
from utils.logging_utils import setup_logging
from processing.job_processor import process_job_site_async
from utils.performance_utils import get_tracker
from templates.prompt_registry import verify_registry


async def main_async():
    """
    Main async function to handle processing with better error handling.
    """
    if len(sys.argv) < 2:
        print("Usage: python main.py <input_folder> [output_folder]")
        return 1

    job_folder = sys.argv[1]
    output_folder = (
        sys.argv[2] if len(sys.argv) > 2 else os.path.join(job_folder, "output")
    )

    if not os.path.exists(job_folder):
        print(f"Error: Input folder '{job_folder}' does not exist.")
        return 1

    # Generate run_id once for this entire run
    run_id = time.strftime("%Y%m%d_%H%M%S")

    # 1) Set up logging
    setup_logging(output_folder, run_id)
    logging.info(f"Processing files from: {job_folder}")
    logging.info(f"Output will be saved to: {output_folder}")
    logging.info(f"Run ID: {run_id}")
    logging.info(f"Application settings: {get_all_settings()}")
    
    # Log critical settings for visibility
    settings = get_all_settings()
    logging.info("=== Model & Token Configuration ===")
    logging.info(f"⚙️  DEFAULT_MODEL: {settings.get('DEFAULT_MODEL')}")
    logging.info(f"⚙️  LARGE_DOC_MODEL: {settings.get('LARGE_DOC_MODEL')}")
    logging.info(f"⚙️  SCHEDULE_MODEL: {settings.get('SCHEDULE_MODEL')}")
    logging.info(f"⚙️  TINY_MODEL: {settings.get('TINY_MODEL') or 'disabled'}")
    logging.info(f"⚙️  ACTUAL_MODEL_MAX_COMPLETION_TOKENS: {settings.get('ACTUAL_MODEL_MAX_COMPLETION_TOKENS')}")
    logging.info(f"⚙️  DEFAULT_MODEL_MAX_TOKENS: {settings.get('DEFAULT_MODEL_MAX_TOKENS')}")
    logging.info(f"⚙️  LARGE_MODEL_MAX_TOKENS: {settings.get('LARGE_MODEL_MAX_TOKENS')}")
    logging.info(f"⚙️  SPEC_MAX_TOKENS: {os.getenv('SPEC_MAX_TOKENS', '16384')}")
    logging.info(f"⚙️  RESPONSES_TIMEOUT_SECONDS: {settings.get('RESPONSES_TIMEOUT_SECONDS')}")
    logging.info(f"⚙️  NANO_CHAR_THRESHOLD: {settings.get('NANO_CHAR_THRESHOLD')}")
    logging.info(f"⚙️  MINI_CHAR_THRESHOLD: {settings.get('MINI_CHAR_THRESHOLD')}")
    logging.info("=== OCR Configuration ===")
    logging.info(
        f"⚙️  OCR_MODEL: {os.getenv('OCR_MODEL', 'gpt-4o-mini')}, "
        f"OCR_TOKENS_PER_TILE: {os.getenv('OCR_TOKENS_PER_TILE', '3000')}, "
        f"OCR_DPI: {os.getenv('OCR_DPI', '300')}, "
        f"OCR_GRID_SIZE: {os.getenv('OCR_GRID_SIZE', '1')}"
    )
    logging.info("===================================")

    try:
        # Verify prompt registry is fully populated
        if not verify_registry():
            logging.warning("Prompt registry may not be fully populated!")

        # 2) Create OpenAI Client (v1.66.3)
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)

        # 3) Record start time
        start_time = time.time()

        # 4) Run asynchronous job processing
        await process_job_site_async(job_folder, output_folder, client)

        # 5) Calculate total processing time
        total_time = time.time() - start_time
        logging.info(f"Total processing time: {total_time:.2f} seconds")

        # 6) Generate performance report
        tracker = get_tracker()
        tracker.log_report()

        # Save metrics to file for historical comparison
        metrics_file = tracker.save_metrics_v2(output_folder, run_id)
        if not metrics_file:
            logging.warning(
                "Failed to save performance metrics - check permissions and disk space"
            )

        # Check for API performance degradation
        slowdown = tracker.detect_api_slowdown(threshold_percent=40.0)
        if slowdown:
            logging.warning(
                f"API PERFORMANCE ALERT: {slowdown['percent_increase']:.1f}% slower than historical average"
            )
            logging.warning(
                f"Current avg: {slowdown['current_avg']:.2f}s, Historical avg: {slowdown['historical_avg']:.2f}s"
            )

        return 0
    except Exception as e:
        logging.error(f"Unhandled exception in main process: {str(e)}")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main_async())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        sys.exit(1)
