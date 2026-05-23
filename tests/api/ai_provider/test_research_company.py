"""Tests for the non-streaming OpenRouterProvider.research_company path."""
from __future__ import annotations

import json

import pytest

from api.ai_provider.provider import OpenRouterProvider


@pytest.fixture
def provider(fake_api_key, isolated_app_dir):
    return OpenRouterProvider()


def _resp(body: dict, status: int = 200):
    # Build a fake requests.Response-like object directly (research_company
    # uses non-streaming requests.post(...) and reads .json())
    class _R:
        status_code = status
        text = json.dumps(body)

        def raise_for_status(self):
            if status >= 400:
                import requests
                raise requests.HTTPError(f"HTTP {status}")

        @staticmethod
        def json():
            return body

    return _R()


def _success_body(content: str, usage: dict | None = None) -> dict:
    body: dict = {
        "choices": [{"message": {"content": content}}],
    }
    if usage is not None:
        body["usage"] = usage
    return body


class TestResearchCompany:
    def test_happy_path_returns_normalized_dict(self, provider, mocker):
        body = _success_body(json.dumps({
            "core_values": ["one", "two"],
            "recent_projects": ["proj-a"],
            "summary": "Acme is great",
        }))
        mocker.patch("api.ai_provider.provider.requests.post",
                     return_value=_resp(body))
        out = provider.research_company("Acme", "scraped content")
        assert out == {
            "core_values": ["one", "two"],
            "recent_projects": ["proj-a"],
            "summary": "Acme is great",
        }

    def test_strips_markdown_fence(self, provider, mocker):
        wrapped = '```json\n{"core_values": [], "recent_projects": [], "summary": "ok"}\n```'
        mocker.patch("api.ai_provider.provider.requests.post",
                     return_value=_resp(_success_body(wrapped)))
        out = provider.research_company("Acme", "data")
        assert out["summary"] == "ok"

    def test_non_list_core_values_becomes_empty_list(self, provider, mocker):
        body = _success_body(json.dumps({
            "core_values": "not a list",
            "recent_projects": [123, "ok", ""],
            "summary": 42,
        }))
        mocker.patch("api.ai_provider.provider.requests.post",
                     return_value=_resp(body))
        out = provider.research_company("Acme", "data")
        assert out["core_values"] == []
        assert out["recent_projects"] == ["123", "ok"]  # stringified, empty dropped
        assert out["summary"] == "42"

    def test_malformed_json_raises_value_error(self, provider, mocker):
        body = _success_body("not json at all")
        mocker.patch("api.ai_provider.provider.requests.post",
                     return_value=_resp(body))
        with pytest.raises(ValueError, match="unexpected format"):
            provider.research_company("Acme", "data")

    def test_missing_api_key_raises_before_http(self, mocker, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        p = OpenRouterProvider()
        post = mocker.patch("api.ai_provider.provider.requests.post")
        with pytest.raises(ValueError, match="No API key"):
            p.research_company("Acme", "data")
        post.assert_not_called()

    def test_records_usage_when_present(self, provider, mocker):
        body = _success_body(
            json.dumps({"core_values": [], "recent_projects": [], "summary": "ok"}),
            usage={"prompt_tokens": 10, "completion_tokens": 20},
        )
        rec = mocker.patch("api.ai_provider.provider.record_usage")
        mocker.patch("api.ai_provider.provider.requests.post",
                     return_value=_resp(body))
        provider.research_company("Acme", "data")
        rec.assert_called_once_with("fast", 10, 20)
