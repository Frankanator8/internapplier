"""App-wide (non-AI) settings persisted in ``settings.json``.

AI-specific settings (models, API key, resume template, score thresholds)
live in :mod:`api.ai_provider.settings`. The two modules share the same
on-disk file via :mod:`api._settings_base`.
"""
from __future__ import annotations

import pathlib
from typing import Any

from .constants import (
    DEFAULT_AUTO_RESYNC_PROMPTS,
    DEFAULT_HEATMAP_DAY_THRESHOLDS,
    DEFAULT_HEATMAP_WEEK_THRESHOLDS,
    DEFAULT_RESUME_OUTPUT_DIR,
    DEFAULT_SCRAPER_CANDIDATE_PATHS,
)
from ._settings_base import _get, _load_settings, _set


def get_theme_preference() -> str:
    val = str(_get("theme_preference", "system"))
    return val if val in ("light", "dark", "system") else "system"


def save_theme_preference(mode: str) -> None:
    if mode not in ("light", "dark", "system"):
        mode = "system"
    _set("theme_preference", mode)


def _valid_thresholds(val: Any) -> list[int] | None:
    if not isinstance(val, list) or len(val) != 4:
        return None
    try:
        ints = [int(x) for x in val]
    except (TypeError, ValueError):
        return None
    if not all(ints[i] < ints[i + 1] for i in range(3)):
        return None
    return ints


def get_heatmap_day_thresholds() -> list[int]:
    val = _valid_thresholds(_load_settings().get("heatmap_day_thresholds"))
    return val if val is not None else list(DEFAULT_HEATMAP_DAY_THRESHOLDS)


def save_heatmap_day_thresholds(values: list[int]) -> None:
    _set("heatmap_day_thresholds", sorted(int(v) for v in values))


def get_heatmap_week_thresholds() -> list[int]:
    val = _valid_thresholds(_load_settings().get("heatmap_week_thresholds"))
    return val if val is not None else list(DEFAULT_HEATMAP_WEEK_THRESHOLDS)


def save_heatmap_week_thresholds(values: list[int]) -> None:
    _set("heatmap_week_thresholds", sorted(int(v) for v in values))


def get_resume_output_dir() -> pathlib.Path:
    val = _load_settings().get("resume_output_dir")
    if not val:
        return DEFAULT_RESUME_OUTPUT_DIR
    return pathlib.Path(str(val)).expanduser()


def save_resume_output_dir(path: str) -> None:
    _set("resume_output_dir", str(path).strip())


def get_scraper_candidate_paths() -> list[str]:
    val = _load_settings().get("scraper_candidate_paths")
    if isinstance(val, list) and all(isinstance(p, str) for p in val):
        return val
    return DEFAULT_SCRAPER_CANDIDATE_PATHS


def save_scraper_candidate_paths(paths: list[str]) -> None:
    _set("scraper_candidate_paths", [str(p) for p in paths])


def get_writing_sample() -> str:
    val = _load_settings().get("writing_sample")
    return val if isinstance(val, str) else ""


def save_writing_sample(text: str) -> None:
    _set("writing_sample", str(text or ""))


def get_auto_resync_prompts() -> bool:
    return bool(_get("auto_resync_prompts", DEFAULT_AUTO_RESYNC_PROMPTS))


def save_auto_resync_prompts(enabled: bool) -> None:
    _set("auto_resync_prompts", bool(enabled))
