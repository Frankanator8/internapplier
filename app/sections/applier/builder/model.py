"""Widget-free model helpers for the resume builder: ids, MIME payloads, palette."""
from __future__ import annotations

import copy
import json
import uuid
from typing import Callable

from PyQt6.QtCore import QMimeData

MIME_TYPE = "application/x-internapplier-resume-item"

KIND_LABELS = {
    "experience": "Experience",
    "project": "Project",
    "education": "Education",
    "award": "Award",
    "skills": "Skills",
    "hobbies": "Interests",
    "text": "Text",
}

_DEFAULT_SECTION_TITLES = {
    "experience": "Relevant Experience",
    "project": "Projects",
    "education": "Education",
    "award": "Achievements",
    "skills": "Technical Skills",
    "hobbies": "Interests",
    "text": "Additional",
    "section": "New Section",
}


def new_id() -> str:
    return uuid.uuid4().hex[:10]


def default_section_title(kind: str, data: dict | None = None) -> str:
    if kind == "experience" and (data or {}).get("category") == "other":
        return "Leadership Experience"
    return _DEFAULT_SECTION_TITLES.get(kind, "Section")


def encode_payload(payload: dict) -> QMimeData:
    mime = QMimeData()
    mime.setData(MIME_TYPE, json.dumps(payload).encode("utf-8"))
    return mime


def decode_payload(mime: QMimeData | None) -> dict | None:
    if mime is None or not mime.hasFormat(MIME_TYPE):
        return None
    try:
        return json.loads(bytes(mime.data(MIME_TYPE)).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, TypeError):
        return None


def split_csv(text: str) -> list[str]:
    return [p.strip() for p in (text or "").split(",") if p.strip()]


def join_csv(items: list) -> str:
    return ", ".join(str(s).strip() for s in items if str(s).strip())


def _join_label(first: str, second: str, sep: str, fallback: str) -> str:
    first, second = first.strip(), second.strip()
    return f"{first}{sep}{second}" if first and second else first or second or fallback


def _pair_label(first: str, second: str, sep: str, fallback: str) -> Callable[[dict], str]:
    return lambda e: _join_label(e.get(first) or "", e.get(second) or "", sep, fallback)


def _experience_label(entry: dict) -> str:
    title = entry.get("title") or entry.get("role") or ""
    return _join_label(title, entry.get("company") or "", " @ ", "Experience")


# (palette group, profile key, item kind, label function)
_ENTRY_GROUPS: list[tuple[str, str, str, Callable[[dict], str]]] = [
    ("Experience", "experience", "experience", _experience_label),
    ("Projects", "projects", "project", lambda e: (e.get("name") or "").strip() or "Project"),
    ("Education", "education", "education", _pair_label("school", "degree", " — ", "Education")),
    ("Awards", "awards", "award", _pair_label("title", "issuer", " — ", "Award")),
]
# (palette group, profile key, item kind, section label)
_LIST_GROUPS = [
    ("Skills", "skills", "skills", "Skills"),
    ("Hobbies", "hobbies", "hobbies", "Interests"),
]


def palette_groups(profile: dict) -> list[tuple[str, list[dict]]]:
    """Build (group title, leaf payloads) from a profile dict."""
    profile = profile or {}
    groups: list[tuple[str, list[dict]]] = []
    for group, key, kind, make_label in _ENTRY_GROUPS:
        groups.append((group, [
            {"kind": kind, "label": make_label(entry), "data": copy.deepcopy(entry)}
            for entry in profile.get(key) or []
            if isinstance(entry, dict)
        ]))
    for group, key, kind, section_label in _LIST_GROUPS:
        items = [str(s).strip() for s in (profile.get(key) or []) if str(s).strip()]
        preview = ", ".join(items[:4]) + ("…" if len(items) > 4 else "")
        groups.append((group, [
            {"kind": kind, "label": preview, "data": {"items": items, "label": section_label}}
        ] if items else []))
    groups.append(("Building blocks", [
        {"kind": "section", "label": "Section header", "data": {"title": "New Section"}},
        {"kind": "text", "label": "Free-text block", "data": {"body": ""}},
    ]))
    return groups
