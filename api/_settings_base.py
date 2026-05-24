"""Shared helpers for typed get/set against settings.json.

Both ``api.ai_provider.settings`` and ``api.app_settings`` use the same
on-disk file (``SETTINGS_FILE``); they just expose different keys. This
module owns the cache so writes from one module are visible to the other.
"""
from __future__ import annotations

from typing import Any, Callable

from .constants import SETTINGS_FILE
from .json_store import load_json, save_json

_settings_cache: dict | None = None


def _load_settings() -> dict:
    global _settings_cache
    if _settings_cache is not None:
        return _settings_cache
    data = load_json(SETTINGS_FILE, {})
    _settings_cache = data if isinstance(data, dict) else {}
    return _settings_cache


def _invalidate() -> None:
    global _settings_cache
    _settings_cache = None


def _get(key: str, default: Any, coerce: Callable[[Any], Any] | None = None) -> Any:
    val = _load_settings().get(key, default)
    if coerce is None:
        return val
    try:
        return coerce(val)
    except (TypeError, ValueError):
        return default


def _set(key: str, value: Any) -> None:
    global _settings_cache
    current = dict(_load_settings())
    current[key] = value
    save_json(SETTINGS_FILE, current)
    _settings_cache = current
