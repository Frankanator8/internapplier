"""AI-provider-specific settings (models, API key, resume tuning).

Non-AI app settings (theme, heatmap, output dir, writing sample, etc.)
live in :mod:`api.app_settings`. Both share the same ``settings.json``
via :mod:`api._settings_base`.
"""
from __future__ import annotations

import os

from .._settings_base import _get, _set
from ..constants import (
    APP_DIR,
    DEFAULT_BASIC_MODEL,
    DEFAULT_FAST_MODEL,
    DEFAULT_MAX_GENERATION_ATTEMPTS,
    DEFAULT_POWERFUL_MODEL,
    DEFAULT_RESUME_PAGE_CAP,
    DEFAULT_RESUME_SCORE_THRESHOLD,
    ENV_FILE,
    MODELS_FILE,
)
from .prompts import _seed_prompts

_model_config_cache: dict[str, str] | None = None


def get_resume_template() -> str:
    return str(_get("resume_template", ""))


def save_resume_template(text: str) -> None:
    _set("resume_template", text)


def get_resume_page_cap() -> int:
    n = _get("resume_page_cap", DEFAULT_RESUME_PAGE_CAP, int)
    return n if n >= 1 else DEFAULT_RESUME_PAGE_CAP


def save_resume_page_cap(pages: int) -> None:
    _set("resume_page_cap", int(pages))


def get_max_generation_attempts() -> int:
    n = _get("max_generation_attempts", DEFAULT_MAX_GENERATION_ATTEMPTS, int)
    return n if n >= 1 else DEFAULT_MAX_GENERATION_ATTEMPTS


def save_max_generation_attempts(n: int) -> None:
    _set("max_generation_attempts", int(n))


def get_resume_score_threshold() -> float:
    return _get("resume_score_threshold", DEFAULT_RESUME_SCORE_THRESHOLD, float)


def save_resume_score_threshold(value: float) -> None:
    _set("resume_score_threshold", float(value))


def get_openrouter_api_key() -> str:
    """Read the OpenRouter API key from the Application Support .env file."""
    if not ENV_FILE.exists():
        return ""
    try:
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip()
    except OSError:
        return ""
    return ""


def save_openrouter_api_key(key: str) -> None:
    """Persist the OpenRouter API key to the Application Support .env file
    and update the current process environment so changes take effect immediately."""
    APP_DIR.mkdir(parents=True, exist_ok=True)
    key = (key or "").strip()

    lines: list[str] = []
    if ENV_FILE.exists():
        try:
            lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []

    new_line = f"OPENROUTER_API_KEY={key}"
    found = False
    for i, line in enumerate(lines):
        if line.startswith("OPENROUTER_API_KEY="):
            lines[i] = new_line
            found = True
            break
    if not found:
        lines.append(new_line)

    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if key:
        os.environ["OPENROUTER_API_KEY"] = key
    else:
        os.environ.pop("OPENROUTER_API_KEY", None)


def _load_model_config() -> dict[str, str]:
    global _model_config_cache
    if _model_config_cache is not None:
        return _model_config_cache

    defaults = {
        "basic": DEFAULT_BASIC_MODEL,
        "fast": DEFAULT_FAST_MODEL,
        "powerful": DEFAULT_POWERFUL_MODEL,
    }

    APP_DIR.mkdir(parents=True, exist_ok=True)
    _seed_prompts()
    if not MODELS_FILE.exists():
        with open(MODELS_FILE, "w", encoding="utf-8") as f:
            f.write(f"basic={DEFAULT_BASIC_MODEL}\n")
            f.write(f"fast={DEFAULT_FAST_MODEL}\n")
            f.write(f"powerful={DEFAULT_POWERFUL_MODEL}\n")
        _model_config_cache = defaults
        return _model_config_cache

    config = dict(defaults)
    with open(MODELS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip().lower()
            value = value.strip()
            if key in defaults and value:
                config[key] = value

    _model_config_cache = config
    return _model_config_cache


def save_model_config(basic: str, fast: str, powerful: str) -> None:
    global _model_config_cache
    APP_DIR.mkdir(parents=True, exist_ok=True)
    basic = basic.strip()
    fast = fast.strip()
    powerful = powerful.strip()
    with open(MODELS_FILE, "w", encoding="utf-8") as f:
        f.write(f"basic={basic}\n")
        f.write(f"fast={fast}\n")
        f.write(f"powerful={powerful}\n")
    _model_config_cache = {"basic": basic, "fast": fast, "powerful": powerful}
