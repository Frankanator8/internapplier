import json
import os
import pathlib

_APP_DIR = pathlib.Path.home() / "Library" / "Application Support" / "InternApplier"
_DATA_FILE = _APP_DIR / "resume.json"
_TEMPLATE_FILE = _APP_DIR / "interview_template.json"
_FEEDBACK_FILE = _APP_DIR / "interview_feedback.json"

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


def _migrate_application_links(data: dict) -> bool:
    apps = data.get("applications")
    if not isinstance(apps, list):
        return False
    changed = False
    for entry in apps:
        if not isinstance(entry, dict):
            continue
        if "links" not in entry:
            old = entry.get("link", "")
            entry["links"] = [old] if isinstance(old, str) and old else []
            changed = True
        if "link" in entry:
            del entry["link"]
            changed = True
    return changed


def load() -> dict:
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    if not _DATA_FILE.exists():
        return {k: list(v) for k, v in _EMPTY.items()}
    with open(_DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if _migrate_application_links(data):
        save(data)
    return data


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


def load_interview_feedback() -> list[dict]:
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    if not _FEEDBACK_FILE.exists():
        return []
    with open(_FEEDBACK_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        sessions = data.get("sessions")
        return sessions if isinstance(sessions, list) else []
    return data if isinstance(data, list) else []


def save_interview_feedback(sessions: list[dict]) -> None:
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _FEEDBACK_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"sessions": sessions}, f, indent=2)
    os.replace(tmp, _FEEDBACK_FILE)


def append_interview_feedback(session: dict) -> None:
    sessions = load_interview_feedback()
    sessions.append(session)
    save_interview_feedback(sessions)
