from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
from playwright.sync_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from .ai_provider import get_scraper_candidate_paths
from .constants import (
    SCRAPER_MAX_PAGES,
    SCRAPER_MAX_TOTAL_CHARS,
    SCRAPER_USER_AGENT,
)

logger = logging.getLogger(__name__)

_WS_RE = re.compile(r"\s+")


class SiteBlockedError(Exception):
    """Site exists but stalls/blocks our automated browser."""


def _normalize_base(base_url: str) -> tuple[str, str]:
    parsed = urlparse(base_url.strip())
    if not parsed.scheme:
        parsed = urlparse("https://" + base_url.strip())
    if not parsed.netloc:
        raise ValueError(f"Invalid URL: {base_url!r}")
    root = f"{parsed.scheme}://{parsed.netloc}"
    return root, parsed.scheme


def _load_robots(context, root: str) -> RobotFileParser:
    rp = RobotFileParser()
    rp.set_url(urljoin(root, "/robots.txt"))
    try:
        resp = context.request.get(
            urljoin(root, "/robots.txt"), timeout=10000
        )
        if resp.status >= 400:
            rp.parse([])
        else:
            rp.parse(resp.text().splitlines())
    except PlaywrightError:
        rp.parse([])
    return rp


def _extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return _WS_RE.sub(" ", text).strip()


def fetch_company_pages(base_url: str, timeout: int = 15) -> str:
    """Fetch a shallow set of pages from a company site via headless Chromium.

    Returns concatenated plain text. Raises ValueError if robots.txt disallows
    the root URL or no usable content could be extracted. Raises
    SiteBlockedError if every page request timed out (likely WAF/anti-bot).
    """
    root, _ = _normalize_base(base_url)
    candidate_paths = get_scraper_candidate_paths()

    chunks: list[str] = []
    total = 0
    fetched = 0
    errors = 0
    attempted = 0
    seen: set[str] = set()

    with sync_playwright() as p:
        # --disable-http2 works around Akamai/F5 servers that send malformed
        # HTTP/2 frames to non-allowlisted clients (ERR_HTTP2_PROTOCOL_ERROR).
        browser = p.chromium.launch(
            headless=True, args=["--disable-http2"]
        )
        try:
            context = browser.new_context(user_agent=SCRAPER_USER_AGENT)
            rp = _load_robots(context, root)

            if not rp.can_fetch(SCRAPER_USER_AGENT, root + "/"):
                raise ValueError(
                    f"robots.txt for {root} disallows scraping the homepage — aborting."
                )

            page = context.new_page()

            for path in candidate_paths:
                if fetched >= SCRAPER_MAX_PAGES:
                    break
                url = urljoin(root, path)
                if url in seen:
                    continue
                seen.add(url)
                if not rp.can_fetch(SCRAPER_USER_AGENT, url):
                    continue

                attempted += 1
                try:
                    resp = page.goto(
                        url, wait_until="load", timeout=timeout * 1000
                    )
                except PlaywrightTimeoutError:
                    logger.info("fetch_company_pages: timeout on %s", url)
                    errors += 1
                    continue
                except PlaywrightError as exc:
                    logger.info("fetch_company_pages: error on %s: %s", url, exc)
                    errors += 1
                    continue

                # Best-effort wait for JS-heavy sites to finish rendering.
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except PlaywrightTimeoutError:
                    pass

                if resp is None:
                    logger.info("fetch_company_pages: no response for %s", url)
                    continue
                if not resp.ok:
                    logger.info("fetch_company_pages: %s -> HTTP %d", url, resp.status)
                    continue
                ctype = (resp.headers.get("content-type") or "")
                if "html" not in ctype.lower():
                    logger.info("fetch_company_pages: %s non-html (%s)", url, ctype)
                    continue

                try:
                    html = page.content()
                except PlaywrightError as exc:
                    logger.info("fetch_company_pages: content() failed on %s: %s", url, exc)
                    continue
                text = _extract_text(html)
                logger.info(
                    "fetch_company_pages: %s -> html=%d chars, text=%d chars",
                    url, len(html), len(text),
                )
                if not text:
                    continue

                header = f"\n\n--- {url} ---\n\n"
                remaining = SCRAPER_MAX_TOTAL_CHARS - total - len(header)
                if remaining <= 0:
                    break
                snippet = text[:remaining]
                chunks.append(header + snippet)
                total += len(header) + len(snippet)
                fetched += 1
        finally:
            browser.close()

    if fetched == 0:
        if attempted > 0 and errors == attempted:
            raise SiteBlockedError(
                f"{root} refused or stalled every request — it may be blocking "
                f"automated browsers."
            )
        raise ValueError(
            f"Could not fetch any pages from {root} (non-HTML responses, empty "
            f"content, or all paths blocked by robots.txt)."
        )

    return "".join(chunks).strip()
