from __future__ import annotations

from .constants import (
    INTERVIEW_FEEDBACK_FILE,
    INTERVIEW_TEMPLATE_FILE,
    RESUME_DATA_FILE,
)
from .json_store import load_json, save_json


class ApplicationNotFound(KeyError):
    """Raised when an application uuid is not present in the profile."""


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


def _empty_data() -> dict:
    return {k: (list(v) if isinstance(v, list) else dict(v)) for k, v in _EMPTY.items()}


def invalidate() -> None:
    global _cache, _cache_mtime
    _cache = None
    _cache_mtime = None


def load() -> dict:
    global _cache, _cache_mtime
    if not RESUME_DATA_FILE.exists():
        invalidate()
        return _empty_data()
    mtime = RESUME_DATA_FILE.stat().st_mtime
    if _cache is not None and _cache_mtime == mtime:
        return _cache
    data = load_json(RESUME_DATA_FILE, _empty_data())
    _cache = data
    _cache_mtime = mtime
    return _cache


def save(data: dict) -> None:
    global _cache, _cache_mtime
    save_json(RESUME_DATA_FILE, data)
    _cache = data
    _cache_mtime = RESUME_DATA_FILE.stat().st_mtime


def find_application_by_uuid(uuid: str) -> tuple[int, dict] | None:
    apps = load().get("applications") or []
    for i, entry in enumerate(apps):
        if isinstance(entry, dict) and entry.get("uuid") == uuid:
            return i, entry
    return None


def set_application_resume_pdf(uuid: str, pdf_path: str) -> dict:
    data = load()
    apps = data.get("applications") or []
    for i, entry in enumerate(apps):
        if isinstance(entry, dict) and entry.get("uuid") == uuid:
            entry["resume_pdf"] = pdf_path
            apps[i] = entry
            data["applications"] = apps
            save(data)
            return entry
    raise ApplicationNotFound(uuid)


def attach_application_link(uuid: str, url: str) -> list[str]:
    data = load()
    apps = data.get("applications") or []
    for i, entry in enumerate(apps):
        if isinstance(entry, dict) and entry.get("uuid") == uuid:
            links = entry.get("links")
            if not isinstance(links, list):
                links = []
            if url not in links:
                links.append(url)
            entry["links"] = links
            apps[i] = entry
            data["applications"] = apps
            save(data)
            return links
    raise ApplicationNotFound(uuid)


def load_interview_template() -> list[dict]:
    data = load_json(INTERVIEW_TEMPLATE_FILE, None)
    if data is None:
        return [dict(x) for x in _DEFAULT_TEMPLATE]
    return data if isinstance(data, list) else [dict(x) for x in _DEFAULT_TEMPLATE]


def save_interview_template(items: list[dict]) -> None:
    save_json(INTERVIEW_TEMPLATE_FILE, items)


def load_interview_feedback() -> list[dict]:
    data = load_json(INTERVIEW_FEEDBACK_FILE, None)
    if data is None:
        return []
    if isinstance(data, dict):
        sessions = data.get("sessions")
        return sessions if isinstance(sessions, list) else []
    return data if isinstance(data, list) else []


def save_interview_feedback(sessions: list[dict]) -> None:
    save_json(INTERVIEW_FEEDBACK_FILE, {"sessions": sessions})


def append_interview_feedback(session: dict) -> None:
    sessions = load_interview_feedback()
    sessions.append(session)
    save_interview_feedback(sessions)
