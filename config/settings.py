"""
Application settings loaded from environment variables.
"""
import os
import logging
from dotenv import load_dotenv
from typing import Dict, Any

# Load environment variables from .env file
load_dotenv()

# OpenAI API Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY must be set in environment variables")

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Pipeline-specific log level control
PIPELINE_LOG_LEVEL = os.getenv("PIPELINE_LOG_LEVEL", "").upper()

def _resolve_pipeline_level(default=logging.WARNING):
    """Resolve pipeline logging level from environment or defaults."""
    if PIPELINE_LOG_LEVEL in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        return getattr(logging, PIPELINE_LOG_LEVEL, default)
    # If DEBUG_MODE is true, default to INFO for pipeline modules
    return logging.INFO if DEBUG_MODE else default

# Processing Configuration
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))
API_RATE_LIMIT = int(os.getenv("API_RATE_LIMIT", "60"))
TIME_WINDOW = int(os.getenv("TIME_WINDOW", "60"))
# Maximum concurrent API calls
MAX_CONCURRENT_API_CALLS = int(os.getenv("MAX_CONCURRENT_API_CALLS", "20"))

# OCR Configuration - Simple with production safety
OCR_ENABLED = os.getenv("OCR_ENABLED", "true").lower() == "true"
OCR_THRESHOLD = int(os.getenv("OCR_THRESHOLD", "1500"))  # Characters per page threshold (not total)
OCR_MAX_PAGES = int(os.getenv("OCR_MAX_PAGES", "2"))

# Model Selection Configuration - Define as a function to reload each time
def get_force_mini_model():
    """Get the FORCE_MINI_MODEL setting from environment"""
    # Respect the process environment; do not reload .env here
    return os.getenv("FORCE_MINI_MODEL", "false").lower() == "true"


# Standard definition for backward compatibility
FORCE_MINI_MODEL = get_force_mini_model()

# Metadata repair toggle (dynamic)
def get_enable_metadata_repair():
    """Get the ENABLE_METADATA_REPAIR setting from environment"""
    # Respect the process environment; do not reload .env here
    return os.getenv("ENABLE_METADATA_REPAIR", "false").lower() == "true"

# Standard definition for backward compatibility
ENABLE_METADATA_REPAIR = get_enable_metadata_repair()

# Model Configuration - Defaults updated for Responses (gpt-5)
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-5-mini")
LARGE_DOC_MODEL = os.getenv("LARGE_DOC_MODEL", "gpt-5")
SCHEDULE_MODEL = os.getenv("SCHEDULE_MODEL", "gpt-5")
TINY_MODEL = os.getenv("TINY_MODEL", "")  # Optional tiny model (e.g., "gpt-5-nano")
TINY_MODEL_THRESHOLD = int(os.getenv("TINY_MODEL_THRESHOLD", "3000"))

# Model Size Thresholds for tiered selection
NANO_CHAR_THRESHOLD = int(os.getenv("NANO_CHAR_THRESHOLD", "3000"))
MINI_CHAR_THRESHOLD = int(os.getenv("MINI_CHAR_THRESHOLD", "15000"))

# Model-specific parameters (future-proof - no hardcoded model name checks)
DEFAULT_MODEL_TEMP = float(os.getenv("DEFAULT_MODEL_TEMP", "0.1"))
DEFAULT_MODEL_MAX_TOKENS = int(os.getenv("DEFAULT_MODEL_MAX_TOKENS", "32768"))  # GPT-4.1 limit
LARGE_MODEL_TEMP = float(os.getenv("LARGE_MODEL_TEMP", "0.1"))
LARGE_MODEL_MAX_TOKENS = int(os.getenv("LARGE_MODEL_MAX_TOKENS", "32768"))  # GPT-4.1 limit
TINY_MODEL_TEMP = float(os.getenv("TINY_MODEL_TEMP", "0.0"))
TINY_MODEL_MAX_TOKENS = int(os.getenv("TINY_MODEL_MAX_TOKENS", "32768"))  # GPT-4.1 Nano also has same limit

# Maximum completion tokens supported by the specific model version being used
# GPT-4.1, GPT-4.1 Mini, and GPT-4.1 Nano all support 32,768 output tokens
# Context window for all variants: ~1 million tokens input
ACTUAL_MODEL_MAX_COMPLETION_TOKENS = int(os.getenv("ACTUAL_MODEL_MAX_COMPLETION_TOKENS", "32768"))

# API timeouts
RESPONSES_TIMEOUT_SECONDS = int(os.getenv("RESPONSES_TIMEOUT_SECONDS", "600"))

# Threshold character count for using GPT-4o instead of GPT-4o-mini
MODEL_UPGRADE_THRESHOLD = int(os.getenv("MODEL_UPGRADE_THRESHOLD", "15000"))

# Template Configuration
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")

# Additional configuration settings
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# Original document storage configuration
ORIGINAL_STORAGE_BACKEND = os.getenv("ORIGINAL_STORAGE_BACKEND", "filesystem").lower()
ORIGINAL_STORAGE_PREFIX = os.getenv("ORIGINAL_STORAGE_PREFIX", "source-documents").strip("/")
AZURE_BLOB_CONNECTION_STRING = os.getenv("AZURE_BLOB_CONNECTION_STRING")
AZURE_BLOB_ACCOUNT_URL = os.getenv("AZURE_BLOB_ACCOUNT_URL")
AZURE_BLOB_CREDENTIAL = os.getenv("AZURE_BLOB_CREDENTIAL")
AZURE_BLOB_SAS_TOKEN = os.getenv("AZURE_BLOB_SAS_TOKEN")
AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER", "construction-drawings")


def get_all_settings() -> Dict[str, Any]:
    return {
        "OPENAI_API_KEY": "***REDACTED***" if OPENAI_API_KEY else None,
        "LOG_LEVEL": LOG_LEVEL,
        "BATCH_SIZE": BATCH_SIZE,
        "API_RATE_LIMIT": API_RATE_LIMIT,
        "TIME_WINDOW": TIME_WINDOW,
        "TEMPLATE_DIR": TEMPLATE_DIR,
        "DEBUG_MODE": DEBUG_MODE,
        "FORCE_MINI_MODEL": get_force_mini_model(),
        "ENABLE_METADATA_REPAIR": get_enable_metadata_repair(),
        "MAX_CONCURRENT_API_CALLS": MAX_CONCURRENT_API_CALLS,
        "MODEL_UPGRADE_THRESHOLD": MODEL_UPGRADE_THRESHOLD,
        "DEFAULT_MODEL": DEFAULT_MODEL,
        "LARGE_DOC_MODEL": LARGE_DOC_MODEL,
        "SCHEDULE_MODEL": SCHEDULE_MODEL,
        "TINY_MODEL": TINY_MODEL,
        "TINY_MODEL_THRESHOLD": TINY_MODEL_THRESHOLD,
        "NANO_CHAR_THRESHOLD": NANO_CHAR_THRESHOLD,
        "MINI_CHAR_THRESHOLD": MINI_CHAR_THRESHOLD,
        "DEFAULT_MODEL_TEMP": DEFAULT_MODEL_TEMP,
        "DEFAULT_MODEL_MAX_TOKENS": DEFAULT_MODEL_MAX_TOKENS,
        "LARGE_MODEL_TEMP": LARGE_MODEL_TEMP,
        "LARGE_MODEL_MAX_TOKENS": LARGE_MODEL_MAX_TOKENS,
        "TINY_MODEL_TEMP": TINY_MODEL_TEMP,
        "TINY_MODEL_MAX_TOKENS": TINY_MODEL_MAX_TOKENS,
        "ACTUAL_MODEL_MAX_COMPLETION_TOKENS": ACTUAL_MODEL_MAX_COMPLETION_TOKENS,
        "RESPONSES_TIMEOUT_SECONDS": RESPONSES_TIMEOUT_SECONDS,
        # OCR Configuration visibility
        "OCR_ENABLED": OCR_ENABLED,
        "OCR_THRESHOLD": OCR_THRESHOLD,
        "OCR_MAX_PAGES": OCR_MAX_PAGES,
        "ORIGINAL_STORAGE_BACKEND": ORIGINAL_STORAGE_BACKEND,
        "ORIGINAL_STORAGE_PREFIX": ORIGINAL_STORAGE_PREFIX,
        "AZURE_BLOB_CONNECTION_STRING": "***REDACTED***" if AZURE_BLOB_CONNECTION_STRING else None,
        "AZURE_BLOB_ACCOUNT_URL": AZURE_BLOB_ACCOUNT_URL,
        "AZURE_BLOB_CREDENTIAL": "***REDACTED***" if AZURE_BLOB_CREDENTIAL else None,
        "AZURE_BLOB_SAS_TOKEN": "***REDACTED***" if AZURE_BLOB_SAS_TOKEN else None,
        "AZURE_BLOB_CONTAINER": AZURE_BLOB_CONTAINER,
    }

# Apply dynamic levels to pipeline modules
for name in [
    "services.ai_service",
    "utils.ai_cache",
    "services.extraction_service",
    "processing.file_processor",
]:
    logging.getLogger(name).setLevel(_resolve_pipeline_level())

# Keep httpx quiet
logging.getLogger("httpx").setLevel(logging.WARNING)
