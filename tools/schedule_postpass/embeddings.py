"""Vector embedding generation for hybrid search."""
from __future__ import annotations

import logging
from typing import List, Optional

try:  # Lazy import so tests still run without OpenAI configured
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency at runtime
    OpenAI = None  # type: ignore

logger = logging.getLogger(__name__)


def generate_embedding(text: str, client: Optional[OpenAI]) -> Optional[List[float]]:
    """Generate a vector embedding for hybrid search (best-effort)."""
    if not client:
        return None
    trimmed = (text or "").strip()
    if not trimmed:
        return None
    try:
        resp = client.embeddings.create(model="text-embedding-3-large", input=trimmed)
    except Exception as exc:  # pragma: no cover - depends on API availability
        logger.warning("Embedding generation failed (skipping vector): %s", exc)
        return None
    return resp.data[0].embedding


def create_embedding_client() -> Optional[OpenAI]:
    """Create an OpenAI client for embeddings (best-effort, returns None on failure)."""
    if not OpenAI:
        return None
    return OpenAI()

