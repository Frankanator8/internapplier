from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from api import web_scraper
from api.web_scraper import SiteBlockedError, _extract_text, _normalize_base


class TestNormalizeBase:
    def test_adds_https_when_missing_scheme(self):
        root, scheme = _normalize_base("example.com")
        assert root == "https://example.com"
        assert scheme == "https"

    def test_keeps_existing_scheme(self):
        root, scheme = _normalize_base("http://example.com/path")
        assert root == "http://example.com"
        assert scheme == "http"

    def test_blank_raises_value_error(self):
        with pytest.raises(ValueError):
            _normalize_base("https://")


class TestExtractText:
    def test_strips_scripts_styles_and_nav(self):
        html = (
            "<html><body><nav>NAV</nav>"
            "<script>BAD</script><style>BAD</style>"
            "<footer>FOOT</footer>"
            "<p>Hello world</p></body></html>"
        )
        out = _extract_text(html)
        assert "Hello world" in out
        assert "NAV" not in out
        assert "BAD" not in out
        assert "FOOT" not in out

    def test_collapses_whitespace(self):
        html = "<p>a    b\n\n c</p>"
        assert _extract_text(html) == "a b c"


class TestFetchCompanyPages:
    def test_robots_disallow_root_raises_value_error(self, mocker, isolated_app_dir):
        # Build a fake playwright context manager
        fake_pw = MagicMock()
        robots = MagicMock()
        robots.can_fetch.return_value = False
        mocker.patch.object(web_scraper, "_load_robots", return_value=robots)
        mocker.patch.object(web_scraper, "sync_playwright", return_value=fake_pw)
        fake_pw.__enter__.return_value.chromium.launch.return_value = MagicMock()
        with pytest.raises(ValueError, match="robots.txt"):
            web_scraper.fetch_company_pages("https://example.com")

    def test_all_timeouts_raise_site_blocked(self, mocker, isolated_app_dir):
        from playwright.sync_api import TimeoutError as PWTimeout

        # Stub robots permissive
        robots = MagicMock()
        robots.can_fetch.return_value = True
        mocker.patch.object(web_scraper, "_load_robots", return_value=robots)

        page = MagicMock()
        page.goto.side_effect = PWTimeout("timeout")
        browser = MagicMock()
        browser.new_context.return_value.new_page.return_value = page
        pw_mgr = MagicMock()
        pw_mgr.__enter__.return_value.chromium.launch.return_value = browser
        mocker.patch.object(web_scraper, "sync_playwright", return_value=pw_mgr)
        with pytest.raises(SiteBlockedError):
            web_scraper.fetch_company_pages(
                "https://example.com",
            )

    def test_happy_path_returns_concatenated_text(self, mocker, isolated_app_dir):
        robots = MagicMock()
        robots.can_fetch.return_value = True
        mocker.patch.object(web_scraper, "_load_robots", return_value=robots)

        resp = MagicMock()
        resp.ok = True
        resp.status = 200
        resp.headers = {"content-type": "text/html"}

        page = MagicMock()
        page.goto.return_value = resp
        page.content.return_value = "<html><body><p>Hello Acme</p></body></html>"

        ctx = MagicMock()
        ctx.new_page.return_value = page

        browser = MagicMock()
        browser.new_context.return_value = ctx

        pw_mgr = MagicMock()
        pw_mgr.__enter__.return_value.chromium.launch.return_value = browser
        mocker.patch.object(web_scraper, "sync_playwright", return_value=pw_mgr)

        # Only one candidate path to keep mock graph small
        mocker.patch.object(web_scraper, "get_scraper_candidate_paths",
                            return_value=["/"])

        out = web_scraper.fetch_company_pages("https://example.com")
        assert "Hello Acme" in out
        assert "https://example.com/" in out  # header line
