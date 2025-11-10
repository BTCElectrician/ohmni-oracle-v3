"""
Pricing table management for AI model costs.
"""
import os
import json
import logging
from typing import Dict

logger = logging.getLogger(__name__)


def _default_pricing_table() -> Dict[str, Dict[str, float]]:
    """
    Base Tier 4 pricing (USD per 1M tokens).
    
    These prices were last updated November 2025. Review monthly for changes.
    Official OpenAI Tier 4 rates as of November 2025.
    """
    return {
        "gpt-4.1": {"input": 2.00, "output": 8.00},
        "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
        "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o-mini-ocr": {"input": 0.15, "output": 0.60},
        "gpt-5": {"input": 1.25, "output": 10.00},
        "gpt-5-mini": {"input": 0.25, "output": 2.00},
        "gpt-5-nano": {"input": 0.05, "output": 0.40},
        "gpt-5o": {"input": 1.25, "output": 10.00},
        "gpt-5o-mini": {"input": 0.15, "output": 0.60},
    }


def load_pricing_table() -> Dict[str, Dict[str, float]]:
    """Load Tier-4 pricing table with optional JSON overrides."""
    table = _default_pricing_table()
    override_raw = os.getenv("METRIC_PRICING_OVERRIDES")
    if not override_raw:
        return table

    try:
        overrides = json.loads(override_raw)
        if isinstance(overrides, dict):
            for model, values in overrides.items():
                if not isinstance(values, dict):
                    continue
                input_price = float(values.get("input", 0.0))
                output_price = float(values.get("output", 0.0))
                table[model] = {"input": input_price, "output": output_price}
    except Exception as exc:
        logger.warning(
            "METRIC_PRICING_OVERRIDES invalid JSON - using defaults (%s)", exc
        )
    return table


# Module-level pricing table (loaded once at import time)
PRICING_TIER_4 = load_pricing_table()

