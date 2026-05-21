from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class _GradeWorker(QObject):
    stream = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(
        self,
        question: str,
        response: str,
        profile: dict,
        company_name: str | None = None,
        company_research: dict | None = None,
        job_description: str | None = None,
    ):
        super().__init__()
        self._question = question
        self._response = response
        self._profile = profile
        self._company_name = company_name
        self._company_research = company_research
        self._job_description = job_description

    def run(self):
        from api.ai_provider import get_provider
        logger.info(
            "_GradeWorker.run — question=%r response_chars=%d company=%r",
            self._question[:80], len(self._response), self._company_name,
        )
        try:
            for chunk in get_provider(tier="fast").grade_interview_response_stream(
                question=self._question,
                response=self._response,
                profile=self._profile,
                company_name=self._company_name,
                company_research=self._company_research,
                job_description=self._job_description,
            ):
                self.stream.emit(chunk)
            self.finished.emit()
        except Exception as exc:
            logger.exception("_GradeWorker.run — failed")
            self.error.emit(str(exc))


class _ChatReplyWorker(QObject):
    stream = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(
        self,
        history: list[dict],
        profile: dict,
        company_name: str | None = None,
        company_research: dict | None = None,
        job_description: str | None = None,
    ):
        super().__init__()
        self._history = history
        self._profile = profile
        self._company_name = company_name
        self._company_research = company_research
        self._job_description = job_description

    def run(self):
        from api.ai_provider import get_provider
        logger.info(
            "_ChatReplyWorker.run — turns=%d company=%r",
            len(self._history), self._company_name,
        )
        try:
            for chunk in get_provider(tier="fast").chat_interview_stream(
                history=self._history,
                profile=self._profile,
                company_name=self._company_name,
                company_research=self._company_research,
                job_description=self._job_description,
            ):
                self.stream.emit(chunk)
            self.finished.emit()
        except Exception as exc:
            logger.exception("_ChatReplyWorker.run — failed")
            self.error.emit(str(exc))


class _FeedbackWorker(QObject):
    stream = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(
        self,
        question: str,
        response: str,
        profile: dict,
        company_name: str | None = None,
        company_research: dict | None = None,
        job_description: str | None = None,
    ):
        super().__init__()
        self._question = question
        self._response = response
        self._profile = profile
        self._company_name = company_name
        self._company_research = company_research
        self._job_description = job_description

    def run(self):
        from api.ai_provider import get_provider
        logger.info(
            "_FeedbackWorker.run — question=%r response_chars=%d",
            self._question[:80], len(self._response),
        )
        try:
            for chunk in get_provider(tier="fast").grade_interview_response_stream(
                question=self._question,
                response=self._response,
                profile=self._profile,
                company_name=self._company_name,
                company_research=self._company_research,
                job_description=self._job_description,
            ):
                self.stream.emit(chunk)
            self.finished.emit()
        except Exception as exc:
            logger.exception("_FeedbackWorker.run — failed")
            self.error.emit(str(exc))


class _NotesWorker(QObject):
    stream = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(
        self,
        history: list[dict],
        prior_notes: str,
        profile: dict,
        company_name: str | None = None,
        company_research: dict | None = None,
        job_description: str | None = None,
    ):
        super().__init__()
        self._history = history
        self._prior_notes = prior_notes
        self._profile = profile
        self._company_name = company_name
        self._company_research = company_research
        self._job_description = job_description

    def run(self):
        from api.ai_provider import get_provider
        logger.info(
            "_NotesWorker.run — turns=%d prior_chars=%d",
            len(self._history), len(self._prior_notes or ""),
        )
        try:
            for chunk in get_provider(tier="fast").summarize_interview_notes_stream(
                history=self._history,
                prior_notes=self._prior_notes,
                profile=self._profile,
                company_name=self._company_name,
                company_research=self._company_research,
                job_description=self._job_description,
            ):
                self.stream.emit(chunk)
            self.finished.emit()
        except Exception as exc:
            logger.exception("_NotesWorker.run — failed")
            self.error.emit(str(exc))
