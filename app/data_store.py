import json
import os
import pathlib

_APP_DIR = pathlib.Path.home() / "Library" / "Application Support" / "InternApplier"
_DATA_FILE = _APP_DIR / "resume.json"

_EMPTY: dict = {
    "experience": [],
    "projects": [],
    "education": [],
    "awards": [],
    "skills": [],
    "hobbies": [],
    "applications": [],
    "research_cache": {},
}


def load() -> dict:
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    if not _DATA_FILE.exists():
        return {k: list(v) for k, v in _EMPTY.items()}
    with open(_DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save(data: dict) -> None:
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _DATA_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, _DATA_FILE)
