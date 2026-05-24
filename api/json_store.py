"""Shared JSON file-store helpers used by data_store, token_usage, and settings.

All callers want the same shape: ensure the parent dir exists, read JSON
returning a default on missing/invalid, write JSON atomically via a .tmp
file and os.replace.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def load_json(path: Path, default: T) -> T:
    """Read JSON from ``path``. Return ``default`` if the file is missing
    or malformed. Does not create the parent directory.
    """
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        logger.exception("json_store: failed to read %s", path)
        return default


def save_json(path: Path, data) -> None:
    """Atomically write ``data`` as JSON to ``path``. Creates parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)
