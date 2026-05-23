"""Tests for keyword_extractor — we stub the NER pipeline so no model is loaded."""
from __future__ import annotations

import pytest

from api.ai_provider import keyword_extractor as kx


@pytest.fixture(autouse=True)
def _stub_ner(monkeypatch):
    def fake_run_ner(model_name, jd):
        if "knowledge" in model_name:
            return [("python", 0.91), ("kubernetes", 0.85)]
        return [("designing apis", 0.8)]

    monkeypatch.setattr(kx, "_run_ner", fake_run_ner)
    kx._extract_cached.cache_clear()


class TestExtractJdKeywords:
    def test_returns_categorized_keywords_and_excerpts(self):
        jd = "Hello world.\n\nRequirements:\nPython expert needed."
        out = kx.extract_jd_keywords(jd)
        phrases = {k["phrase"]: k for k in out["keywords"]}
        assert phrases["python"]["category"] == "knowledge"
        assert phrases["python"]["score"] == 0.91
        assert phrases["designing apis"]["category"] == "skill"
        assert out["excerpts"]

    def test_empty_jd_returns_empty(self):
        out = kx.extract_jd_keywords("")
        assert out == {"keywords": [], "excerpts": []}


class TestFormatJdSignals:
    def test_empty_signals_returns_placeholder(self):
        assert kx.format_jd_signals({}) == "(no signals extracted)"

    def test_groups_by_category_and_includes_excerpts(self):
        out = kx.format_jd_signals({
            "keywords": [
                {"phrase": "python", "score": 0.9, "category": "knowledge"},
                {"phrase": "designing apis", "score": 0.8, "category": "skill"},
            ],
            "excerpts": ["First paragraph."],
        })
        assert "python" in out
        assert "designing apis" in out
        assert "tools / technologies" in out
        assert "methodologies" in out
        assert "First paragraph." in out
        assert "verbatim excerpts" in out

    def test_handles_string_keywords(self):
        out = kx.format_jd_signals({"keywords": ["python", "data"]})
        assert "python" in out and "data" in out
