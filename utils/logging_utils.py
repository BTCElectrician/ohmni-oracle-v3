"""
Logging utilities with structured logging support.
"""
import os
import logging
import sys
from datetime import datetime


def setup_logging(output_folder: str, run_id: str = None) -> None:
    """
    Configure and initialize logging for the application.
    Creates a 'logs' folder in the output directory.
    This version explicitly manages handlers for robustness.

    Args:
        output_folder: Folder to store log files
        run_id: Optional run ID to use in log filename
    """
    log_folder = os.path.join(output_folder, "logs")
    try:
        os.makedirs(log_folder, exist_ok=True)
    except OSError as e:
        # Print to stderr if log directory creation fails
        print(f"Critical Error: Could not create log directory {log_folder}. Error: {e}", file=sys.stderr)
        # Allow to proceed, console logging might still work
        pass

    if run_id is None:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file_name = f"process_log_{run_id}.txt"
    log_file_path = os.path.join(log_folder, log_file_name)

    # --- Step 1: Determine Logging Level ---
    # Get the LOG_LEVEL from environment variable, default to INFO
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    numeric_log_level = getattr(logging, log_level_str, logging.INFO)
    # Fallback for invalid LOG_LEVEL string
    if not isinstance(numeric_log_level, int):
        print(f"Warning: Invalid LOG_LEVEL '{log_level_str}' in environment. Defaulting to INFO.", file=sys.stderr)
        numeric_log_level = logging.INFO
        log_level_str = "INFO"  # Correct the string representation for the confirmation log

    # --- Step 2: Get Root Logger and Set Its Level ---
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_log_level)

    # --- Step 3: Clear Existing Handlers (CRITICAL STEP) ---
    # This prevents interference from pre-configured handlers
    if root_logger.hasHandlers():
        for handler in root_logger.handlers[:]:  # Iterate over a copy
            try:
                handler.close()  # Important to close handlers, especially file handlers
            except Exception:
                pass  # Ignore errors if handler can't be closed
            root_logger.removeHandler(handler)

    # --- Step 4: Define a Common Log Formatter ---
    # Adding %(name)s helps identify the source module of the log message
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)

    # --- Step 5: Configure and Add File Handler ---
    try:
        file_handler = logging.FileHandler(log_file_path, mode='w')  # 'w' to overwrite for each run
        file_handler.setFormatter(formatter)
        file_handler.setLevel(numeric_log_level)  # Handler level respects LOG_LEVEL
        root_logger.addHandler(file_handler)
    except Exception as e:
        # If file handler setup fails, log error to stderr
        print(f"Critical Error: Failed to create file handler for {log_file_path}. Error: {e}", file=sys.stderr)

    # --- Step 6: Configure and Add Console Handler ---
    try:
        console_handler = logging.StreamHandler(sys.stdout)  # Explicitly use sys.stdout
        console_handler.setFormatter(formatter)
        console_handler.setLevel(numeric_log_level)  # Handler level respects LOG_LEVEL
        root_logger.addHandler(console_handler)
    except Exception as e:
        # If console handler setup fails, log error to stderr
        print(f"Critical Error: Failed to create console handler. Error: {e}", file=sys.stderr)

    # --- Step 7: Log Initialization Confirmation ---
    init_logger = logging.getLogger("utils.logging_utils")
    init_logger.info(f"Logging initialized. Effective log level: {log_level_str}. Log file: {log_file_path}")
