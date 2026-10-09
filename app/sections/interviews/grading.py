"""AI grading of interview answers, shared by the question cards and the chat."""
from __future__ import annotations

import logging

from api.interview_parsing import parse_grade_payload
from app.ui.workers import StreamWorker

logger = logging.getLogger(__name__)

GRADE_FORMAT_ERROR = "AI returned unexpected format — please try again."


def grade_worker(question: str, response: str, profile: dict, job: dict | None) -> StreamWorker:
    """Stream a JSON grade for ``response``; ``job`` is an ``api.applications.job_context``."""
    return StreamWorker.provider(
        "grade_interview_response_stream",
        question=question, response=response, profile=profile, **(job or {}),
    )


def parse_grade(buf: str) -> tuple[str, str] | None:
    """``(score text, feedback)`` from a finished grade stream, or None if malformed."""
    try:
        score, feedback = parse_grade_payload(buf)
    except (ValueError, TypeError) as exc:
        logger.error("parse_grade — failed: %s; raw=%r", exc, buf[:500])
        return None
    return f"{score:g}", feedback
