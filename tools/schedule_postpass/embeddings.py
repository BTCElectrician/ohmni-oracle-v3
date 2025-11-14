"""Vector embedding generation for hybrid search."""
from __future__ import annotations

import logging
from typing import List, Optional
import os

try:  # Lazy import so tests still run without OpenAI configured
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency at runtime
    OpenAI = None  # type: ignore

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None  # type: ignore

try:
    import tiktoken  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    tiktoken = None  # type: ignore

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
_MAX_EMBED_TOKENS = 7800  # Keep below text-embedding-3-small 8k context


def generate_embedding(text: str, client: Optional[OpenAI]) -> Optional[List[float]]:
    """Generate a vector embedding for hybrid search (best-effort)."""
    if not client:
        return None
    trimmed = (text or "").strip()
    if not trimmed:
        return None
    if _exceeds_token_limit(trimmed):
        logger.warning("Embedding skipped: content length exceeds %s tokens", _MAX_EMBED_TOKENS)
        return None
    try:
        resp = client.embeddings.create(model=EMBEDDING_MODEL, input=trimmed)
    except Exception as exc:  # pragma: no cover - depends on API availability
        logger.warning("Embedding generation failed (skipping vector): %s", exc)
        return None
    return resp.data[0].embedding


def create_embedding_client() -> Optional[OpenAI]:
    """Create an OpenAI client for embeddings (best-effort, returns None on failure)."""
    if not OpenAI:
        return None
    # Load .env if available to populate OPENAI_API_KEY in subprocess contexts
    if load_dotenv:
        try:
            load_dotenv()
        except Exception:
            pass
    api_key = os.getenv("OPENAI_API_KEY")
    try:
        return OpenAI(api_key=api_key) if api_key else OpenAI()
    except Exception as exc:  # pragma: no cover
        logger.warning("OpenAI client init failed: %s", exc)
        return None


def _exceeds_token_limit(text: str) -> bool:
    if not text:
        return False
    if tiktoken:
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            token_count = len(enc.encode(text, disallowed_special=()))
            return token_count > _MAX_EMBED_TOKENS
        except Exception:
            pass
    # Fallback heuristic: ~4 chars per token
    return len(text) / 4 > _MAX_EMBED_TOKENS

