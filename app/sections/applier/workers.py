from __future__ import annotations

from PyQt6.QtCore import pyqtSignal

from app.ui.workers import Worker


class ResearchWorker(Worker):
    """Scrape a company site and summarize it. ``finished`` carries the result dict."""

    def __init__(self, company_name: str, url: str):
        super().__init__()
        self._company_name = company_name
        self._url = url

    def work(self) -> dict:
        from api.research_cache import research_company_site
        return research_company_site(self._company_name, self._url, self.progress.emit)

    def error_message(self, exc: Exception) -> str:
        from api.web_scraper import SiteBlockedError
        if isinstance(exc, SiteBlockedError):
            return (
                "This site appears to block automated tools — try a different URL "
                "or scrape manually."
            )
        return super().error_message(exc)


class GenerateResumeWorker(Worker):
    """Run the full resume pipeline. ``finished`` carries its payload dict."""

    stream = pyqtSignal(str, str)  # (stage, chunk)

    def __init__(
        self,
        profile: dict,
        jd: str,
        company_name: str,
        url: str,
        research_cache: dict,
        job_title: str = "",
        application_uuid: str | None = None,
    ):
        super().__init__()
        self._kwargs = dict(
            profile=profile,
            job_description=jd,
            company=company_name,
            url=url,
            job_title=job_title,
            application_uuid=application_uuid,
            research_cache=research_cache,
        )

    def work(self) -> dict:
        from api.resume_pipeline import run_resume_pipeline
        return run_resume_pipeline(
            **self._kwargs, progress_cb=self.progress.emit, stream_cb=self.stream.emit,
        )
