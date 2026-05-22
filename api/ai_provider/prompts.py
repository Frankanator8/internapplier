import json
import re

from ..constants import APP_PROMPTS_DIR, PROMPTS_DIR

_PROMPT_EXTS: tuple[str, ...] = (".txt", ".schema.json", ".tool.json")
_SCHEMA_PLACEHOLDER = re.compile(r"\{\{schema:([^}\s]+)\}\}")


def _iter_source_files():
    for ext in _PROMPT_EXTS:
        yield from PROMPTS_DIR.glob(f"*{ext}")


def _prune_orphans(valid_names: set[str]) -> None:
    for ext in _PROMPT_EXTS:
        for path in APP_PROMPTS_DIR.glob(f"*{ext}"):
            if path.name not in valid_names:
                path.unlink()


def _seed_prompts() -> None:
    APP_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    source_names: set[str] = set()
    for src in _iter_source_files():
        source_names.add(src.name)
        dst = APP_PROMPTS_DIR / src.name
        if not dst.exists():
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    _prune_orphans(source_names)


def resync_all_prompts() -> None:
    APP_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    source_names: set[str] = set()
    for src in _iter_source_files():
        source_names.add(src.name)
        dst = APP_PROMPTS_DIR / src.name
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    _prune_orphans(source_names)


def _read_seeded(name: str) -> str:
    return (APP_PROMPTS_DIR / name).read_text(encoding="utf-8")


def load_prompt_raw(name: str) -> str:
    return _read_seeded(name)


def list_prompt_files() -> list[str]:
    names: list[str] = [p.name for p in _iter_source_files()]

    def sort_key(name: str) -> tuple[int, str]:
        if name.endswith(".schema.json"):
            group = 1
        elif name.endswith(".tool.json"):
            group = 2
        else:
            group = 0
        return (group, name.lower())

    return sorted(set(names), key=sort_key)


def load_prompt(name: str) -> str:
    text = _read_seeded(name)

    def _expand(match: re.Match) -> str:
        return _read_seeded(match.group(1)).strip()

    return _SCHEMA_PLACEHOLDER.sub(_expand, text).strip()


def default_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8").strip()


def save_prompt(name: str, content: str) -> None:
    APP_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    (APP_PROMPTS_DIR / name).write_text(content, encoding="utf-8")


def load_schema(name: str) -> dict:
    return json.loads(_read_seeded(name))
