from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup


USER_AGENT = "InternApplierBot/1.0 (+research-only)"

CANDIDATE_PATHS = [
    "/", "/about", "/about-us", "/company", "/values",
    "/mission", "/careers", "/team", "/news", "/blog",
]

MAX_PAGES = 5
MAX_TOTAL_CHARS = 15000
_WS_RE = re.compile(r"\s+")


def _normalize_base(base_url: str) -> tuple[str, str]:
    parsed = urlparse(base_url.strip())
    if not parsed.scheme:
        parsed = urlparse("https://" + base_url.strip())
    if not parsed.netloc:
        raise ValueError(f"Invalid URL: {base_url!r}")
    root = f"{parsed.scheme}://{parsed.netloc}"
    return root, parsed.scheme


def _load_robots(root: str) -> RobotFileParser:
    rp = RobotFileParser()
    rp.set_url(urljoin(root, "/robots.txt"))
    try:
        resp = requests.get(
            urljoin(root, "/robots.txt"),
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        if resp.status_code >= 400:
            rp.parse([])
        else:
            rp.parse(resp.text.splitlines())
    except requests.RequestException:
        rp.parse([])
    return rp


def _extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return _WS_RE.sub(" ", text).strip()


def fetch_company_pages(base_url: str, timeout: int = 10) -> str:
    """Fetch a shallow set of pages from a company site, respecting robots.txt.

    Returns concatenated plain text. Raises ValueError if robots.txt disallows
    the root URL or if no pages could be successfully fetched.
    """
    root, _ = _normalize_base(base_url)
    rp = _load_robots(root)

    if not rp.can_fetch(USER_AGENT, root + "/"):
        raise ValueError(
            f"robots.txt for {root} disallows scraping the homepage — aborting."
        )

    chunks: list[str] = []
    total = 0
    fetched = 0
    seen: set[str] = set()

    for path in CANDIDATE_PATHS:
        if fetched >= MAX_PAGES:
            break
        url = urljoin(root, path)
        if url in seen:
            continue
        seen.add(url)
        if not rp.can_fetch(USER_AGENT, url):
            continue
        try:
            resp = requests.get(
                url, headers={"User-Agent": USER_AGENT}, timeout=timeout
            )
        except requests.RequestException:
            continue
        if resp.status_code != 200:
            continue
        ctype = resp.headers.get("Content-Type", "")
        if "html" not in ctype.lower():
            continue
        text = _extract_text(resp.text)
        if not text:
            continue
        header = f"\n\n--- {url} ---\n\n"
        remaining = MAX_TOTAL_CHARS - total - len(header)
        if remaining <= 0:
            break
        snippet = text[:remaining]
        chunks.append(header + snippet)
        total += len(header) + len(snippet)
        fetched += 1

    if fetched == 0:
        raise ValueError(
            f"Could not fetch any pages from {root} (network errors, "
            f"non-HTML responses, or all paths blocked by robots.txt)."
        )

    return "".join(chunks).strip()
