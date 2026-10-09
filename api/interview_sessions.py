"""Saved interview-practice sessions: building, labelling and rendering them.

Persisted via ``data_store.append_interview_feedback`` / ``load_interview_feedback``.
"""
from __future__ import annotations

import datetime


def build_session(
    *,
    session_id: str,
    started_at: datetime.datetime,
    job: dict | None,
    transcript: list[dict],
    cards: list[dict],
    notes_md: str,
) -> dict:
    """``job`` is ``{"company", "title"}`` or None; ``cards`` are
    ``{"question", "answer", "rubric_md"}`` dicts."""
    return {
        "id": session_id,
        "started_at": started_at.isoformat(timespec="seconds"),
        "ended_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "job": job,
        "transcript": list(transcript),
        "cards": [
            {"question": c["question"], "answer": c["answer"], "rubric_md": c["rubric_md"]}
            for c in cards
        ],
        "notes_md": notes_md,
    }


def session_label(session: dict) -> str:
    started = session.get("started_at", "")[:16].replace("T", " ")
    company = (session.get("job") or {}).get("company") or "Generic"
    return f"{started} — {company}"


def transcript_markdown(session: dict) -> str:
    lines = []
    for turn in session.get("transcript") or []:
        who = "**You:**" if turn.get("role") == "user" else "**Interviewer:**"
        lines.append(f"{who} {turn.get('content', '').strip()}\n")
    return "\n".join(lines)


def cards_markdown(session: dict) -> str:
    lines: list[str] = []
    for card in session.get("cards") or []:
        question = (card.get("question") or "Opening exchange").strip()
        lines.append(f"### Q: {question}\n")
        answer = (card.get("answer") or "").strip()
        if answer:
            lines.append(f"_Your answer:_ {answer}\n")
        lines.append((card.get("rubric_md") or "").strip())
        lines.append("\n---\n")
    return "\n".join(lines)
