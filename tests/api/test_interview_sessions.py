from __future__ import annotations

import datetime

from api.interview_sessions import build_session, cards_markdown, session_label, transcript_markdown


def _session():
    return build_session(
        session_id="abc",
        started_at=datetime.datetime(2026, 1, 2, 3, 4, 5),
        job={"company": "Acme", "title": "SWE"},
        transcript=[{"role": "assistant", "content": "Hi "}, {"role": "user", "content": "Hello"}],
        cards=[{"question": "", "answer": "Hello", "rubric_md": "Good", "buffer": "x"}],
        notes_md="notes",
    )


def test_build_session_shape():
    s = _session()
    assert s["id"] == "abc"
    assert s["started_at"] == "2026-01-02T03:04:05"
    assert s["cards"] == [{"question": "", "answer": "Hello", "rubric_md": "Good"}]
    assert s["notes_md"] == "notes"


def test_session_label():
    assert session_label(_session()) == "2026-01-02 03:04 — Acme"
    assert session_label({"started_at": "2026-01-02T03:04:05"}) == "2026-01-02 03:04 — Generic"


def test_markdown_rendering():
    s = _session()
    assert transcript_markdown(s) == "**Interviewer:** Hi\n\n**You:** Hello\n"
    md = cards_markdown(s)
    assert md.startswith("### Q: Opening exchange\n")
    assert "_Your answer:_ Hello" in md and "Good" in md
