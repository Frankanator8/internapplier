from __future__ import annotations

import logging
from typing import Callable

from . import data_store
from .research_cache import lookup as _research_from_cache

logger = logging.getLogger(__name__)


class ResumePipelineError(Exception):
    """User-facing error from running the resume pipeline."""


def run_resume_pipeline(
    *,
    profile: dict,
    job_description: str,
    company: str,
    url: str,
    job_title: str = "",
    application_uuid: str | None = None,
    research_cache: dict | None = None,
    progress_cb: Callable[[str], None] | None = None,
    stream_cb: Callable[[str, str], None] | None = None,
) -> dict:
    """Scrape company pages, research the company, generate + compile the
    resume, and (if `application_uuid` is given) persist the PDF path onto
    the application.

    Returns a payload shaped like the desktop worker's `finished` signal so
    both the desktop app and the HTTP server can share rendering.
    """
    from .ai_provider import get_provider
    from .generate_resume import ResumeGenerator

    cache = research_cache or {}
    new_research = False
    research = _research_from_cache(cache, company) if company else None
    if research is not None:
        if progress_cb:
            progress_cb(f"Using cached research for {company!r}…")
    elif company and url:
        from .web_scraper import fetch_company_pages
        if progress_cb:
            progress_cb(f"Scraping {url}…")
        text = fetch_company_pages(url)
        if progress_cb:
            progress_cb(f"Scraped {len(text):,} chars — analyzing…")
        research = get_provider().research_company(company, text)
        new_research = True
    else:
        research = {
            "summary": f"{company or 'the target company'} is the target company.",
            "core_values": [],
            "recent_projects": [],
        }

    gen = ResumeGenerator(profile, job_description, research)
    if progress_cb:
        progress_cb("Generating LaTeX (this can take a minute)…")
    latex_result = gen.generate_latex(
        company=company or None,
        job_title=job_title or None,
        progress_cb=progress_cb,
        stream_cb=stream_cb,
    )

    pdf_path = latex_result.get("pdf")
    desired_pdf = latex_result.get("pdf_desired")
    if application_uuid and pdf_path:
        try:
            data_store.set_application_resume_pdf(application_uuid, str(pdf_path))
        except Exception:
            logger.exception(
                "run_resume_pipeline — failed to link resume pdf to %s",
                application_uuid,
            )

    return {
        "research": research,
        "new_research": new_research,
        "latex": latex_result.get("latex", ""),
        "pdf": str(pdf_path) if pdf_path else "",
        "pdf_desired": str(desired_pdf) if desired_pdf else "",
        "pdf_collision": bool(latex_result.get("pdf_collision")),
        "fill": latex_result.get("fill"),
        "grade": latex_result.get("grade"),
        "attempts": latex_result.get("attempts") or [],
        "chosen_attempt": latex_result.get("chosen_attempt"),
    }


def generate_resume_for_application(
    uuid: str,
    *,
    progress_cb: Callable[[str], None] | None = None,
    stream_cb: Callable[[str, str], None] | None = None,
) -> dict:
    """Run the pipeline using inputs sourced from the application entry."""
    found = data_store.find_application_by_uuid(uuid)
    if found is None:
        raise ResumePipelineError("application not found")
    _, app = found

    jd = (app.get("description") or "").strip()
    if not jd:
        raise ResumePipelineError(
            "application has no job description — add one before generating a resume"
        )

    company = (app.get("company") or "").strip()
    job_title = (app.get("role") or "").strip()
    links = app.get("links") or []
    url = links[0] if links else ""
    profile = data_store.load()

    return run_resume_pipeline(
        profile=profile,
        job_description=jd,
        company=company,
        url=url,
        job_title=job_title,
        application_uuid=uuid,
        progress_cb=progress_cb,
        stream_cb=stream_cb,
    )
