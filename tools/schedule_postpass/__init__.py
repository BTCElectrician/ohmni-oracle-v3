"""Schedule post-pass transformation modules."""
from __future__ import annotations

from .coverage import coverage_rows
from .embeddings import create_embedding_client, generate_embedding
from .facts import emit_facts
from .ids import make_document_id, sanitize_key_component, stable_key
from .io_utils import load_json, write_jsonl
from .metadata import make_sheet_doc, sheet_meta
from .template_docs import _collect_sheet_templates, iter_template_docs

__all__ = [
    "coverage_rows",
    "create_embedding_client",
    "emit_facts",
    "generate_embedding",
    "iter_template_docs",
    "load_json",
    "make_document_id",
    "make_sheet_doc",
    "sanitize_key_component",
    "sheet_meta",
    "stable_key",
    "write_jsonl",
    "_collect_sheet_templates",
]

