"""The company research cache: ``{company: {"url": str, "result": dict}}``."""
from __future__ import annotations

from typing import Callable


def lookup(cache: dict, company: str) -> dict | None:
    if not company or not cache:
        return None
    entry = cache.get(company)
    if entry is None:
        for k, v in cache.items():
            if k.lower() == company.lower():
                entry = v
                break
    if entry is None:
        return None
    if isinstance(entry, dict) and "result" in entry and isinstance(entry["result"], dict):
        return entry["result"]
    if isinstance(entry, dict) and {"summary", "core_values", "recent_projects"} & entry.keys():
        return entry
    return None


def store(cache: dict, company: str, url: str, result: dict) -> None:
    cache[company] = {"url": url, "result": result}


def research_company_site(
    company: str, url: str, progress_cb: Callable[[str], None] | None = None,
) -> dict:
    """Scrape ``url`` and ask the AI to summarize ``company`` from it."""
    from .ai_provider import get_provider
    from .web_scraper import fetch_company_pages

    if progress_cb:
        progress_cb(f"Fetching pages from {url}…")
    text = fetch_company_pages(url)
    if progress_cb:
        progress_cb(f"Scraped {len(text):,} chars — asking AI to analyze…")
    return get_provider().research_company(company, text)
