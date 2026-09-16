"""Load/save the drag-and-drop resume builder draft.

Drafts are stored separately from ``resume.json`` so canvas edits never
write back to the user's profile.
"""
from __future__ import annotations

from api import constants
from api.json_store import load_json, save_json


def load_draft() -> dict:
    data = load_json(constants.RESUME_BUILDER_DRAFT_FILE, None)
    if not isinstance(data, dict):
        return {
            "company": "",
            "job_title": "",
            "sections": [],
        }
    sections = data.get("sections")
    if not isinstance(sections, list):
        sections = []
    return {
        "company": data.get("company") or "",
        "job_title": data.get("job_title") or "",
        "sections": sections,
    }


def save_draft(data: dict) -> None:
    payload = {
        "company": (data or {}).get("company") or "",
        "job_title": (data or {}).get("job_title") or "",
        "sections": (data or {}).get("sections") or [],
    }
    save_json(constants.RESUME_BUILDER_DRAFT_FILE, payload)
