import json
import pathlib
from typing import Any, Callable

from ..constants import (
    APP_DIR,
    DEFAULT_AUTO_RESYNC_PROMPTS,
    DEFAULT_FAST_MODEL,
    DEFAULT_MAX_GENERATION_ATTEMPTS,
    DEFAULT_POWERFUL_MODEL,
    DEFAULT_RESUME_OUTPUT_DIR,
    DEFAULT_RESUME_PAGE_CAP,
    DEFAULT_RESUME_SCORE_THRESHOLD,
    DEFAULT_SCRAPER_CANDIDATE_PATHS,
    MODELS_FILE,
    SETTINGS_FILE,
)
from .prompts import _seed_prompts

_settings_cache: dict | None = None
_model_config_cache: dict[str, str] | None = None


def _load_settings() -> dict:
    global _settings_cache
    if _settings_cache is not None:
        return _settings_cache
    if not SETTINGS_FILE.exists():
        _settings_cache = {}
        return _settings_cache
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        _settings_cache = data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        _settings_cache = {}
    return _settings_cache


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
    APP_DIR.mkdir(parents=True, exist_ok=True)
    current = dict(_load_settings())
    current[key] = value
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    _settings_cache = current


def get_resume_template() -> str:
    return str(_get("resume_template", ""))


def save_resume_template(text: str) -> None:
    _set("resume_template", text)


def get_resume_page_cap() -> int:
    n = _get("resume_page_cap", DEFAULT_RESUME_PAGE_CAP, int)
    return n if n >= 1 else DEFAULT_RESUME_PAGE_CAP


def save_resume_page_cap(pages: int) -> None:
    _set("resume_page_cap", int(pages))


def get_resume_output_dir() -> pathlib.Path:
    val = _load_settings().get("resume_output_dir")
    if not val:
        return DEFAULT_RESUME_OUTPUT_DIR
    return pathlib.Path(str(val)).expanduser()


def save_resume_output_dir(path: str) -> None:
    _set("resume_output_dir", str(path).strip())


def get_max_generation_attempts() -> int:
    n = _get("max_generation_attempts", DEFAULT_MAX_GENERATION_ATTEMPTS, int)
    return n if n >= 1 else DEFAULT_MAX_GENERATION_ATTEMPTS


def save_max_generation_attempts(n: int) -> None:
    _set("max_generation_attempts", int(n))


def get_resume_score_threshold() -> float:
    return _get("resume_score_threshold", DEFAULT_RESUME_SCORE_THRESHOLD, float)


def save_resume_score_threshold(value: float) -> None:
    _set("resume_score_threshold", float(value))


def get_scraper_candidate_paths() -> list[str]:
    val = _load_settings().get("scraper_candidate_paths")
    if isinstance(val, list) and all(isinstance(p, str) for p in val):
        return val
    return DEFAULT_SCRAPER_CANDIDATE_PATHS


def save_scraper_candidate_paths(paths: list[str]) -> None:
    _set("scraper_candidate_paths", [str(p) for p in paths])


def get_auto_resync_prompts() -> bool:
    return bool(_get("auto_resync_prompts", DEFAULT_AUTO_RESYNC_PROMPTS))


def save_auto_resync_prompts(enabled: bool) -> None:
    _set("auto_resync_prompts", bool(enabled))


def _load_model_config() -> dict[str, str]:
    global _model_config_cache
    if _model_config_cache is not None:
        return _model_config_cache

    defaults = {"fast": DEFAULT_FAST_MODEL, "powerful": DEFAULT_POWERFUL_MODEL}

    APP_DIR.mkdir(parents=True, exist_ok=True)
    _seed_prompts()
    if not MODELS_FILE.exists():
        with open(MODELS_FILE, "w", encoding="utf-8") as f:
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


def save_model_config(fast: str, powerful: str) -> None:
    global _model_config_cache
    APP_DIR.mkdir(parents=True, exist_ok=True)
    fast = fast.strip()
    powerful = powerful.strip()
    with open(MODELS_FILE, "w", encoding="utf-8") as f:
        f.write(f"fast={fast}\n")
        f.write(f"powerful={powerful}\n")
    _model_config_cache = {"fast": fast, "powerful": powerful}
