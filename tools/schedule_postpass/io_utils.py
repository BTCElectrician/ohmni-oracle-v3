"""I/O utilities for JSON and JSONL files."""
from __future__ import annotations

import json
import pathlib
from typing import Any, Dict, Iterable


def load_json(path: pathlib.Path) -> Dict[str, Any]:
    """Load JSON from a file path."""
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_jsonl(path: pathlib.Path, docs: Iterable[Dict[str, Any]]) -> None:
    """Write documents as JSONL (one JSON object per line)."""
    with path.open("w", encoding="utf-8") as handle:
        for doc in docs:
            doc.pop("raw_json", None)
            handle.write(json.dumps(doc, ensure_ascii=False) + "\n")

