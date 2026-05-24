"""In-process resume-generation job tracker.

The HTTP route fires off a background thread and immediately returns;
clients poll a status endpoint to learn when the PDF is ready. This
module owns the (uuid → job state) map, the lock, and the worker
wrapper. Route handlers should only call :func:`start` / :func:`get`.
"""
from __future__ import annotations

import logging
import threading

from .ai_provider.errors import friendly_error_message
from .resume_pipeline import ResumePipelineError, generate_resume_for_application

logger = logging.getLogger(__name__)

_jobs: dict[str, dict] = {}
_lock = threading.Lock()


class JobAlreadyRunning(RuntimeError):
    """Raised when start() is called for a uuid whose job is still running."""


def _run(uuid: str) -> None:
    try:
        payload = generate_resume_for_application(uuid)
    except ResumePipelineError as exc:
        with _lock:
            _jobs[uuid] = {"status": "error", "error": str(exc)}
        return
    except Exception as exc:
        logger.exception("resume generation failed for %s", uuid)
        with _lock:
            _jobs[uuid] = {"status": "error", "error": friendly_error_message(exc)}
        return
    with _lock:
        _jobs[uuid] = {
            "status": "done",
            "resume_pdf": payload.get("pdf", ""),
        }


def start(uuid: str) -> None:
    """Mark the uuid as running and spawn a daemon worker thread.

    Raises :class:`JobAlreadyRunning` if a job for this uuid is already
    in flight.
    """
    with _lock:
        existing = _jobs.get(uuid)
        if existing and existing.get("status") == "running":
            raise JobAlreadyRunning(uuid)
        _jobs[uuid] = {"status": "running"}
    threading.Thread(target=_run, args=(uuid,), daemon=True).start()


def get(uuid: str) -> dict:
    """Return the current job state for a uuid, or ``{"status": "idle"}``."""
    with _lock:
        entry = _jobs.get(uuid)
        if entry is None:
            return {"status": "idle"}
        return dict(entry)
