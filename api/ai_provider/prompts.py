from .paths import _APP_PROMPTS_DIR, _PROMPTS_DIR


def _seed_prompts() -> None:
    _APP_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    for src in _PROMPTS_DIR.glob("*.txt"):
        dst = _APP_PROMPTS_DIR / src.name
        if not dst.exists():
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def resync_all_prompts() -> None:
    _APP_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    for src in _PROMPTS_DIR.glob("*.txt"):
        dst = _APP_PROMPTS_DIR / src.name
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def load_prompt(name: str) -> str:
    return (_APP_PROMPTS_DIR / name).read_text(encoding="utf-8").strip()


def default_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8").strip()


def save_prompt(name: str, content: str) -> None:
    _APP_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    (_APP_PROMPTS_DIR / name).write_text(content, encoding="utf-8")
