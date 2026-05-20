import json
import os
import pathlib

_APP_DIR = pathlib.Path.home() / "Library" / "Application Support" / "InternApplier"
_DATA_FILE = _APP_DIR / "resume.json"
_TEMPLATE_FILE = _APP_DIR / "interview_template.json"

_EMPTY: dict = {
    "general_info": {},
    "experience": [],
    "projects": [],
    "education": [],
    "awards": [],
    "skills": [],
    "hobbies": [],
    "applications": [],
    "research_cache": {},
}

_DEFAULT_TEMPLATE: list[dict] = [
    {"question": "Why this company?", "answer": ""},
    {"question": "Tell me about yourself", "answer": ""},
]


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


def load_interview_template() -> list[dict]:
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    if not _TEMPLATE_FILE.exists():
        return [dict(x) for x in _DEFAULT_TEMPLATE]
    with open(_TEMPLATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else [dict(x) for x in _DEFAULT_TEMPLATE]


def save_interview_template(items: list[dict]) -> None:
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _TEMPLATE_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)
    os.replace(tmp, _TEMPLATE_FILE)
