import json
import os

from .constants import (
    APP_DIR,
    INTERVIEW_FEEDBACK_FILE,
    INTERVIEW_TEMPLATE_FILE,
    RESUME_DATA_FILE,
)

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

_cache: dict | None = None
_cache_mtime: float | None = None


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


def _migrate_research_cache(data: dict) -> bool:
    cache = data.get("research_cache")
    if not isinstance(cache, dict):
        cache = {}
        data["research_cache"] = cache
    if cache:
        if "research" in data:
            del data["research"]
            return True
        return False
    old = data.get("research") or {}
    changed = False
    if isinstance(old, dict) and old.get("company_name") and old.get("result"):
        cache[old["company_name"]] = {
            "url": old.get("url", ""),
            "result": old["result"],
        }
        changed = True
    if "research" in data:
        del data["research"]
        changed = True
    return changed


def _empty_data() -> dict:
    return {k: (list(v) if isinstance(v, list) else dict(v)) for k, v in _EMPTY.items()}


def invalidate() -> None:
    global _cache, _cache_mtime
    _cache = None
    _cache_mtime = None


def load() -> dict:
    global _cache, _cache_mtime
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if not RESUME_DATA_FILE.exists():
        invalidate()
        return _empty_data()
    mtime = RESUME_DATA_FILE.stat().st_mtime
    if _cache is not None and _cache_mtime == mtime:
        return _cache
    with open(RESUME_DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    changed = False
    if _migrate_application_links(data):
        changed = True
    if _migrate_research_cache(data):
        changed = True
    if changed:
        save(data)
        return _cache  # type: ignore[return-value]
    _cache = data
    _cache_mtime = mtime
    return _cache


def save(data: dict) -> None:
    global _cache, _cache_mtime
    APP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = RESUME_DATA_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, RESUME_DATA_FILE)
    _cache = data
    _cache_mtime = RESUME_DATA_FILE.stat().st_mtime


def load_interview_template() -> list[dict]:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if not INTERVIEW_TEMPLATE_FILE.exists():
        return [dict(x) for x in _DEFAULT_TEMPLATE]
    with open(INTERVIEW_TEMPLATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else [dict(x) for x in _DEFAULT_TEMPLATE]


def save_interview_template(items: list[dict]) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = INTERVIEW_TEMPLATE_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)
    os.replace(tmp, INTERVIEW_TEMPLATE_FILE)


def load_interview_feedback() -> list[dict]:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if not INTERVIEW_FEEDBACK_FILE.exists():
        return []
    with open(INTERVIEW_FEEDBACK_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        sessions = data.get("sessions")
        return sessions if isinstance(sessions, list) else []
    return data if isinstance(data, list) else []


def save_interview_feedback(sessions: list[dict]) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = INTERVIEW_FEEDBACK_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"sessions": sessions}, f, indent=2)
    os.replace(tmp, INTERVIEW_FEEDBACK_FILE)


def append_interview_feedback(session: dict) -> None:
    sessions = load_interview_feedback()
    sessions.append(session)
    save_interview_feedback(sessions)
