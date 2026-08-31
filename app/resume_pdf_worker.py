"""Off-thread resume-PDF import: read the file, then ask the AI to structure it.

Shared by the main window's toolbar action and the onboarding wizard. There is
deliberately no cancel: the long leg is a single blocking ``requests.post`` and
``requests`` offers no interrupt, so callers disable their entry points for the
duration and join the thread via ``shutdown_threads`` on teardown instead.
"""
from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class ResumePdfImportWorker(QObject):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, pdf_path: str):
        super().__init__()
        self._pdf_path = pdf_path

    def run(self):
        from api import resume_pdf_import
        from api.ai_provider.errors import friendly_error_message

        logger.info("ResumePdfImportWorker.run — path=%r", self._pdf_path)
        try:
            self.progress.emit("Reading PDF…")
            text = resume_pdf_import.extract_text(self._pdf_path)

            self.progress.emit(
                f"Extracted {len(text):,} characters — asking AI to structure it…"
            )
            data = resume_pdf_import.parse_text(text)

            logger.info(
                "ResumePdfImportWorker.run — success, %s",
                resume_pdf_import.summarize(data),
            )
            self.finished.emit(data)
        except (resume_pdf_import.ResumePdfError, ValueError) as exc:
            # Both carry messages written for the user.
            logger.warning("ResumePdfImportWorker.run — %s", exc)
            self.error.emit(str(exc))
        except Exception as exc:
            logger.exception("ResumePdfImportWorker.run — failed")
            self.error.emit(friendly_error_message(exc))
