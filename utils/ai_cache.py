"""
Caching utility for AI responses to avoid redundant API calls.
"""
import os
import json
import hashlib
import time
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

CACHE_DIR = os.getenv("AI_CACHE_DIR", ".ai_cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def _generate_cache_key(prompt: str, params: Dict[str, Any]) -> str:
    """
    Generate a unique cache key based on prompt and parameters.

    Args:
        prompt: The content prompt
        params: Model parameters (temperature, model, etc.)

    Returns:
        A unique hash string to use as cache key
    """
    # Include key parameters in the hash to ensure cache validity
    key_data = {
        "prompt": prompt,
        "model": params.get("model", ""),
        "temperature": params.get("temperature", 0.0),
        "max_tokens": params.get("max_tokens", 0),
    }

    # Create a stable string representation and hash it
    key_str = json.dumps(key_data, sort_keys=True)
    h = hashlib.sha256(key_str.encode()).hexdigest()
    return h


def _get_cache_path(cache_key: str) -> str:
    """
    Get the file path for a cache key.

    Args:
        cache_key: The cache key

    Returns:
        Path to the cache file
    """
    return os.path.join(CACHE_DIR, f"{cache_key}.json")


def load_cache(prompt: str, params: Dict[str, Any]) -> Optional[str]:
    """
    Load cached response if available.

    Args:
        prompt: The content prompt
        params: Model parameters

    Returns:
        Cached response or None if not found
    """
    if os.getenv("ENABLE_AI_CACHE", "false").lower() != "true":
        return None

    cache_key = _generate_cache_key(prompt, params)
    cache_path = _get_cache_path(cache_key)

    if not os.path.exists(cache_path):
        return None

    # Check cache TTL (default 24 hours)
    ttl_hours = float(os.getenv("AI_CACHE_TTL_HOURS", "24"))
    file_age_hours = (time.time() - os.path.getmtime(cache_path)) / 3600

    if file_age_hours > ttl_hours:
        logger.info(
            f"Cache expired for key {cache_key[:8]}... (age: {file_age_hours:.1f}h)"
        )
        return None

    try:
        with open(cache_path, "r") as f:
            cache_data = json.load(f)
            logger.info(f"Cache hit for key {cache_key[:8]}...")
            return cache_data.get("response")
    except (json.JSONDecodeError, KeyError, IOError) as e:
        logger.warning(f"Failed to load cache: {str(e)}")
        return None


def save_cache(prompt: str, params: Dict[str, Any], response: str) -> None:
    """
    Save response to cache.

    Args:
        prompt: The content prompt
        params: Model parameters
        response: The response to cache
    """
    if os.getenv("ENABLE_AI_CACHE", "false").lower() != "true":
        return

    cache_key = _generate_cache_key(prompt, params)
    cache_path = _get_cache_path(cache_key)

    try:
        cache_data = {
            "prompt": prompt,
            "params": {
                k: params[k]
                for k in ["model", "temperature", "max_tokens"]
                if k in params
            },
            "response": response,
            "timestamp": time.time(),
        }

        with open(cache_path, "w") as f:
            json.dump(cache_data, f, indent=2)

        logger.info(f"Cached response for key {cache_key[:8]}...")
    except IOError as e:
        logger.warning(f"Failed to save cache: {str(e)}")
