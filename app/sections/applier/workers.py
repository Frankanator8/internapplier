from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, pyqtSignal

from api.ai_provider.errors import friendly_error_message as _friendly
from api.research_cache import lookup as _research_from_cache

logger = logging.getLogger(__name__)


class _ResearchWorker(QObject):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, company_name: str, url: str):
        super().__init__()
        self._company_name = company_name
        self._url = url

    def run(self):
        from api.ai_provider import get_provider
        from api.web_scraper import SiteBlockedError, fetch_company_pages
        logger.info("_ResearchWorker.run — company=%r url=%r", self._company_name, self._url)
        try:
            self.progress.emit(f"Fetching pages from {self._url}…")
            text = fetch_company_pages(self._url)
            logger.debug("_ResearchWorker.run — scraped %d chars", len(text))
            self.progress.emit(f"Scraped {len(text):,} chars — asking AI to analyze…")
            result = get_provider().research_company(self._company_name, text)
            logger.info("_ResearchWorker.run — success")
            self.finished.emit(result)
        except SiteBlockedError:
            logger.exception("_ResearchWorker.run — site blocked")
            self.error.emit(
                "This site appears to block automated tools — try a different URL "
                "or scrape manually."
            )
        except Exception as exc:
            logger.exception("_ResearchWorker.run — failed")
            self.error.emit(_friendly(exc))


class _GenerateResumeWorker(QObject):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)
    stream = pyqtSignal(str, str)  # (stage, chunk)

    def __init__(self, profile: dict, jd: str, company_name: str, url: str, research_cache: dict, job_title: str = "", application_uuid: str | None = None):
        super().__init__()
        self._profile = profile
        self._jd = jd
        self._company = company_name
        self._url = url
        self._job_title = job_title
        self._cache = research_cache or {}
        self._application_uuid = application_uuid

    def run(self):
        from api.resume_pipeline import run_resume_pipeline
        logger.info("_GenerateResumeWorker.run — company=%r jd=%r", self._company, self._jd[:80])
        try:
            payload = run_resume_pipeline(
                profile=self._profile,
                job_description=self._jd,
                company=self._company,
                url=self._url,
                job_title=self._job_title,
                application_uuid=self._application_uuid,
                research_cache=self._cache,
                progress_cb=self.progress.emit,
                stream_cb=self.stream.emit,
            )
            logger.info("_GenerateResumeWorker.run — success, fill=%s", payload.get("fill"))
            self.finished.emit(payload)
        except Exception as exc:
            logger.exception("_GenerateResumeWorker.run — failed")
            self.error.emit(_friendly(exc))


class _QuestionWorker(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    stream = pyqtSignal(str)

    def __init__(self, question: str, profile: dict, company_name: str, job_description: str, research_cache: dict):
        super().__init__()
        self._question = question
        self._profile = profile
        self._company = company_name
        self._jd = job_description
        self._cache = research_cache or {}

    def run(self):
        from api.ai_provider import get_provider
        logger.info(
            "_QuestionWorker.run — company=%r question=%r jd=%s",
            self._company, self._question[:80],
            f"{len(self._jd)} chars" if self._jd else "none",
        )
        try:
            research = _research_from_cache(self._cache, self._company) if self._company else None
            for chunk in get_provider().answer_question_stream(
                question=self._question,
                profile=self._profile,
                company_research=research,
                company_name=self._company or None,
                job_description=self._jd or None,
            ):
                self.stream.emit(chunk)
            self.finished.emit()
        except Exception as exc:
            logger.exception("_QuestionWorker.run — failed")
            self.error.emit(_friendly(exc))
