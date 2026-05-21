from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, pyqtSignal

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
            self.error.emit(str(exc))


class _GenerateResumeWorker(QObject):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)
    stream = pyqtSignal(str, str)  # (stage, chunk)

    def __init__(self, profile: dict, jd: str, company_name: str, url: str, research_cache: dict):
        super().__init__()
        self._profile = profile
        self._jd = jd
        self._company = company_name
        self._url = url
        self._cache = research_cache or {}

    def run(self):
        from api.ai_provider import get_provider
        from api.generate_resume import ResumeGenerator
        logger.info("_GenerateResumeWorker.run — company=%r jd=%r", self._company, self._jd[:80])
        try:
            new_research = False
            research = _research_from_cache(self._cache, self._company)
            if research is not None:
                self.progress.emit(f"Using cached research for {self._company!r}…")
            elif self._company and self._url:
                from api.web_scraper import fetch_company_pages
                self.progress.emit(f"Scraping {self._url}…")
                text = fetch_company_pages(self._url)
                self.progress.emit(f"Scraped {len(text):,} chars — analyzing…")
                research = get_provider().research_company(self._company, text)
                new_research = True
            else:
                research = {
                    "summary": f"{self._company or 'the target company'} is the target company.",
                    "core_values": [],
                    "recent_projects": [],
                }

            gen = ResumeGenerator(self._profile, self._jd, research)

            self.progress.emit("Generating LaTeX (this can take a minute)…")
            latex_result = gen.generate_latex(
                company=self._company or None,
                progress_cb=self.progress.emit,
                stream_cb=self.stream.emit,
            )

            pdf_path = latex_result.get("pdf")
            logger.info(
                "_GenerateResumeWorker.run — success, fill=%s",
                latex_result.get("fill"),
            )
            self.finished.emit({
                "research": research,
                "new_research": new_research,
                "latex": latex_result.get("latex", ""),
                "pdf": str(pdf_path) if pdf_path else "",
                "fill": latex_result.get("fill"),
                "grade": latex_result.get("grade"),
                "attempts": latex_result.get("attempts") or [],
                "chosen_attempt": latex_result.get("chosen_attempt"),
            })
        except Exception as exc:
            logger.exception("_GenerateResumeWorker.run — failed")
            self.error.emit(str(exc))


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
            self.error.emit(str(exc))
