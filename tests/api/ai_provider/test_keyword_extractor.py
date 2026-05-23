"""Tests for keyword_extractor — we mock KeyBERT so no model is loaded."""
from __future__ import annotations

import pytest

from api.ai_provider import keyword_extractor as kx


@pytest.fixture(autouse=True)
def _stub_keybert(monkeypatch):
    class _FakeKB:
        def extract_keywords(self, jd, **kwargs):
            return [("python", 0.91), ("data", 0.7)]

    monkeypatch.setattr(kx, "_keybert_instance", _FakeKB())
    # Clear the lru_cache so re-runs are deterministic
    kx._extract_cached.cache_clear()


class TestExtractJdKeywords:
    def test_returns_keywords_and_excerpts(self):
        jd = "Hello world.\n\nRequirements:\nPython expert needed."
        out = kx.extract_jd_keywords(jd)
        assert {"phrase": "python", "score": 0.91} in out["keywords"]
        assert out["excerpts"]

    def test_empty_jd_returns_empty(self):
        out = kx.extract_jd_keywords("")
        assert out == {"keywords": [], "excerpts": []}


class TestFormatJdSignals:
    def test_empty_signals_returns_placeholder(self):
        assert kx.format_jd_signals({}) == "(no signals extracted)"

    def test_includes_keywords_and_excerpts(self):
        out = kx.format_jd_signals({
            "keywords": [{"phrase": "python", "score": 0.9}],
            "excerpts": ["First paragraph."],
        })
        assert "python" in out
        assert "First paragraph." in out
        assert "keywords" in out and "verbatim excerpts" in out

    def test_handles_string_keywords(self):
        out = kx.format_jd_signals({"keywords": ["python", "data"]})
        assert "python" in out and "data" in out
