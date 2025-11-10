"""
Configuration and environment variable loading for performance tracking.
"""
import os
import logging

logger = logging.getLogger(__name__)

# Tier-4 pricing limits and workday configuration
TIER4_MONTHLY_LIMIT = float(os.getenv("TIER4_MONTHLY_LIMIT", "5000"))
WORKDAY_HOURS = float(os.getenv("METRICS_WORKDAY_HOURS", "8"))
WORKDAYS_PER_MONTH = float(os.getenv("METRICS_WORKDAYS_PER_MONTH", "20"))

# Storage metrics
STORAGE_PER_1000_FILES_GB = float(os.getenv("METRICS_STORAGE_PER_1000_FILES_GB", "12.5"))
AZURE_STORAGE_COST_PER_GB = float(os.getenv("METRICS_STORAGE_COST_PER_GB", "0.20"))

# Token and baseline metrics
METRICS_AVG_CHARS_PER_TOKEN = float(os.getenv("METRICS_AVG_CHARS_PER_TOKEN", "4"))
BASELINE_AVG_TIME = float(os.getenv("METRICS_BASELINE_AVG_TIME", "86.62"))
BASELINE_DATE = os.getenv("METRICS_BASELINE_DATE", "2025-11-09")
BASELINE_ACCEPTABLE_MIN = float(os.getenv("METRICS_BASELINE_MIN", "85"))
BASELINE_ACCEPTABLE_MAX = float(os.getenv("METRICS_BASELINE_MAX", "105"))
BASELINE_COST_PER_DRAWING = float(os.getenv("METRICS_BASELINE_COST_PER_DRAWING", "0.04"))

