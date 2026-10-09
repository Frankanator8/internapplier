from __future__ import annotations

import logging
from collections import deque

from PyQt6.QtCore import QObject, pyqtSignal

from app.context import AppContext
from app.ui.workers import WorkerPool

from ..applier.workers import GenerateResumeWorker

logger = logging.getLogger(__name__)


class PrepAllRunner(QObject):
    """Generates resumes for a batch of applications, one at a time.

    Jobs are application dicts, identified by object identity rather than row
    index, so deleting rows mid-batch can't redirect a result to the wrong
    application. ``job_done`` is emitted with the job's entry on success.
    """

    progress = pyqtSignal(str)
    job_done = pyqtSignal(object)
    all_done = pyqtSignal()

    def __init__(self, ctx: AppContext, parent: QObject):
        super().__init__(parent)
        self._ctx = ctx
        self._pool = WorkerPool(self)
        self._queue: deque[dict] = deque()

    @property
    def running(self) -> bool:
        return bool(self._queue) or self._pool.busy

    def start(self, entries: list[dict]) -> None:
        self._queue = deque(entries)
        self._next()

    def _next(self) -> None:
        if not self._queue:
            self.progress.emit("✓  Done.")
            self.all_done.emit()
            return

        entry = self._queue.popleft()
        jd = (entry.get("description") or "").strip()
        company = (entry.get("company") or "").strip()
        if not jd:
            logger.info("Prep All: skipping %r — no description", company)
            self.progress.emit(f"Skipped {company or 'row'} — no JD.")
            self._next()
            return

        links = entry.get("links") or []
        self.progress.emit(
            f"Generating for {company or 'application'}… ({len(self._queue)} more queued)"
        )

        def on_finished(_payload: dict):
            self.job_done.emit(entry)
            self._next()

        def on_error(msg: str):
            logger.error("Prep All: %r failed — %s", company, msg)
            self.progress.emit(f"Error on {company or 'row'}: {msg}")
            self._next()

        self._pool.start(
            GenerateResumeWorker(
                self._ctx.get_profile(), jd, company,
                (links[0] if links else "").strip(),
                self._ctx.research.to_dict(),
                (entry.get("role") or "").strip(),
                application_uuid=entry.get("uuid"),
            ),
            progress=lambda msg: self.progress.emit(f"{company}: {msg}"),
            finished=on_finished,
            error=on_error,
        )
