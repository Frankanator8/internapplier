"""Pure helpers over tracked-application dicts."""
from __future__ import annotations


def app_label(entry: dict, fallback: str = "(untitled)") -> str:
    """``"Company — Role"``, either half alone, or ``fallback``."""
    parts = [(entry.get(k) or "").strip() for k in ("company", "role")]
    return " — ".join(p for p in parts if p) or fallback


def job_context(entry: dict, research: dict | None) -> dict:
    """Keyword args describing a job for the interview-practice AI calls."""
    return {
        "company_name": entry.get("company") or None,
        "company_research": research,
        "job_description": entry.get("description") or None,
    }
