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

# Processing Configuration
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))
API_RATE_LIMIT = int(os.getenv("API_RATE_LIMIT", "60"))
TIME_WINDOW = int(os.getenv("TIME_WINDOW", "60"))
# Maximum concurrent API calls
MAX_CONCURRENT_API_CALLS = int(os.getenv("MAX_CONCURRENT_API_CALLS", "20"))

# Processing Mode Configuration
# DEPRECATED: This setting is no longer actively used in the codebase
USE_SIMPLIFIED_PROCESSING = (
    os.getenv("USE_SIMPLIFIED_PROCESSING", "false").lower() == "true"
)

# Optionally log a warning when loaded
if os.getenv("USE_SIMPLIFIED_PROCESSING") is not None:
    logging.warning("USE_SIMPLIFIED_PROCESSING is deprecated and will be removed in a future version")

# Model Selection Configuration - Define as a function to reload each time
def get_force_mini_model():
    """Always reload from env to get the latest value"""
    load_dotenv(override=True)
    return os.getenv("FORCE_MINI_MODEL", "false").lower() == "true"


# Standard definition for backward compatibility
FORCE_MINI_MODEL = get_force_mini_model()

# Model Configuration - Easy to change when new models come out
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
LARGE_DOC_MODEL = os.getenv("LARGE_DOC_MODEL", "gpt-4o")
SCHEDULE_MODEL = os.getenv("SCHEDULE_MODEL", "gpt-4o")
TINY_MODEL = os.getenv("TINY_MODEL", "")  # Optional tiny model
TINY_MODEL_THRESHOLD = int(os.getenv("TINY_MODEL_THRESHOLD", "3000"))

# Model-specific parameters (future-proof - no hardcoded model name checks)
DEFAULT_MODEL_TEMP = float(os.getenv("DEFAULT_MODEL_TEMP", "0.1"))
DEFAULT_MODEL_MAX_TOKENS = int(os.getenv("DEFAULT_MODEL_MAX_TOKENS", "16000"))
LARGE_MODEL_TEMP = float(os.getenv("LARGE_MODEL_TEMP", "0.1"))
LARGE_MODEL_MAX_TOKENS = int(os.getenv("LARGE_MODEL_MAX_TOKENS", "16000"))
TINY_MODEL_TEMP = float(os.getenv("TINY_MODEL_TEMP", "0.0"))
TINY_MODEL_MAX_TOKENS = int(os.getenv("TINY_MODEL_MAX_TOKENS", "8000"))

# Maximum completion tokens supported by the specific model version being used
ACTUAL_MODEL_MAX_COMPLETION_TOKENS = int(os.getenv("ACTUAL_MODEL_MAX_COMPLETION_TOKENS", "32000"))

# Threshold character count for using GPT-4o instead of GPT-4o-mini
MODEL_UPGRADE_THRESHOLD = int(os.getenv("MODEL_UPGRADE_THRESHOLD", "15000"))

# Whether to use GPT-4o for schedule drawings regardless of size
USE_4O_FOR_SCHEDULES = os.getenv("USE_4O_FOR_SCHEDULES", "true").lower() == "true"

# Template Configuration
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")

# Additional configuration settings
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"


def get_all_settings() -> Dict[str, Any]:
    return {
        "OPENAI_API_KEY": "***REDACTED***" if OPENAI_API_KEY else None,
        "LOG_LEVEL": LOG_LEVEL,
        "BATCH_SIZE": BATCH_SIZE,
        "API_RATE_LIMIT": API_RATE_LIMIT,
        "TIME_WINDOW": TIME_WINDOW,
        "TEMPLATE_DIR": TEMPLATE_DIR,
        "DEBUG_MODE": DEBUG_MODE,
        "USE_SIMPLIFIED_PROCESSING": USE_SIMPLIFIED_PROCESSING,
        "FORCE_MINI_MODEL": get_force_mini_model(),  # Always get latest value
        "MAX_CONCURRENT_API_CALLS": MAX_CONCURRENT_API_CALLS,
        "MODEL_UPGRADE_THRESHOLD": MODEL_UPGRADE_THRESHOLD,
        "USE_4O_FOR_SCHEDULES": USE_4O_FOR_SCHEDULES,
        "DEFAULT_MODEL": DEFAULT_MODEL,
        "LARGE_DOC_MODEL": LARGE_DOC_MODEL,
        "SCHEDULE_MODEL": SCHEDULE_MODEL,
        "TINY_MODEL": TINY_MODEL,
        "TINY_MODEL_THRESHOLD": TINY_MODEL_THRESHOLD,
        "DEFAULT_MODEL_TEMP": DEFAULT_MODEL_TEMP,
        "DEFAULT_MODEL_MAX_TOKENS": DEFAULT_MODEL_MAX_TOKENS,
        "LARGE_MODEL_TEMP": LARGE_MODEL_TEMP,
        "LARGE_MODEL_MAX_TOKENS": LARGE_MODEL_MAX_TOKENS,
        "TINY_MODEL_TEMP": TINY_MODEL_TEMP,
        "TINY_MODEL_MAX_TOKENS": TINY_MODEL_MAX_TOKENS,
        "ACTUAL_MODEL_MAX_COMPLETION_TOKENS": ACTUAL_MODEL_MAX_COMPLETION_TOKENS,
    }

# Reduce logging noise from verbose modules
logging.getLogger("services.ai_service").setLevel(logging.WARNING)
logging.getLogger("utils.ai_cache").setLevel(logging.WARNING) 
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("services.extraction_service").setLevel(logging.WARNING)
logging.getLogger("processing.file_processor").setLevel(logging.WARNING)
