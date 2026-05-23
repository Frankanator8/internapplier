"""Tests that each public stream method on OpenRouterProvider builds the
expected request payload — system prompt name, tier→model, special
features (response_format, sampling, tools)."""
from __future__ import annotations

import pytest

from api.ai_provider.provider import OpenRouterProvider


@pytest.fixture
def provider(fake_api_key, isolated_app_dir):
    # isolated_app_dir so load_prompt() reads from a fresh seeded dir
    return OpenRouterProvider()


@pytest.fixture(autouse=True)
def _stub_model_config(monkeypatch):
    monkeypatch.setattr(
        "api.ai_provider.provider._load_model_config",
        lambda: {"basic": "B", "fast": "F", "powerful": "P"},
    )


def _stop_event(sse_factory):
    return [sse_factory.delta(finish_reason="stop")]


class TestAnalyzeBullet:
    def test_tier_basic_and_user_block(self, provider, mock_openrouter, sse_factory):
        mock_openrouter.queue_stream(_stop_event(sse_factory))
        list(provider.analyze_bullet_stream(
            "Built a thing",
            context={"type": "experience", "company": "Acme", "role": "SWE"},
        ))
        payload = mock_openrouter.last_payload()
        assert payload["model"] == "B"
        user_msg = payload["messages"][1]["content"]
        assert "Built a thing" in user_msg
        assert "Acme" in user_msg and "SWE" in user_msg
        # No tools, no response_format, no sampling
        assert "tools" not in payload
        assert "response_format" not in payload
        assert "temperature" not in payload


class TestGradeResume:
    def test_tier_fast_no_tools(self, provider, mock_openrouter, sse_factory,
                                sample_resume_json, sample_jd):
        mock_openrouter.queue_stream(_stop_event(sse_factory))
        list(provider.grade_resume_stream(
            sample_resume_json, sample_jd, fill=0.92, page_cap=1.0,
            today="2026-01-01",
        ))
        payload = mock_openrouter.last_payload()
        assert payload["model"] == "F"
        assert "tools" not in payload
        user_msg = payload["messages"][1]["content"]
        assert "2026-01-01" in user_msg
        assert "fill=0.92" in user_msg
        assert sample_jd.strip() in user_msg

    def test_omits_page_status_when_fill_none(
            self, provider, mock_openrouter, sse_factory, sample_resume_json, sample_jd):
        mock_openrouter.queue_stream(_stop_event(sse_factory))
        list(provider.grade_resume_stream(
            sample_resume_json, sample_jd, today="2026-01-01",
        ))
        user_msg = mock_openrouter.last_payload()["messages"][1]["content"]
        assert "page_status" not in user_msg

    def test_includes_research_block(
            self, provider, mock_openrouter, sse_factory, sample_resume_json, sample_jd):
        mock_openrouter.queue_stream(_stop_event(sse_factory))
        list(provider.grade_resume_stream(
            sample_resume_json, sample_jd,
            company_research={"summary": "Acme is great"},
            today="2026-01-01",
        ))
        user_msg = mock_openrouter.last_payload()["messages"][1]["content"]
        assert "Acme is great" in user_msg
        assert "<company_research>" in user_msg


class TestGenerateResume:
    def test_tier_powerful_with_tools(
            self, provider, mock_openrouter, sse_factory, monkeypatch,
            sample_profile, sample_jd):
        # Stub the KeyBERT extractor — no model load in tests
        monkeypatch.setattr(
            "api.ai_provider.keyword_extractor.extract_jd_keywords",
            lambda jd, top_n=30: {"keywords": [], "excerpts": []},
        )
        mock_openrouter.queue_stream(_stop_event(sse_factory))
        list(provider.generate_resume_stream(
            sample_profile, sample_jd, today="2026-01-01",
        ))
        payload = mock_openrouter.last_payload()
        assert payload["model"] == "P"
        # Tool calling is set up for this method
        assert payload["tools"]
        assert payload["tools"][0]["function"]["name"] == "page_length"
        assert payload["tool_choice"] == "auto"


class TestAnswerQuestion:
    def test_tier_basic_with_sampling(
            self, provider, mock_openrouter, sse_factory, sample_profile):
        mock_openrouter.queue_stream(_stop_event(sse_factory))
        list(provider.answer_question_stream(
            "Why join us?", sample_profile, today="2026-01-01",
        ))
        payload = mock_openrouter.last_payload()
        assert payload["model"] == "B"
        assert payload["temperature"] == 0.9
        assert payload["frequency_penalty"] == 0.4
        assert payload["presence_penalty"] == 0.2
        # No tools
        assert "tools" not in payload


class TestGradeInterviewResponse:
    def test_tier_fast_with_response_format(
            self, provider, mock_openrouter, sse_factory, sample_profile):
        mock_openrouter.queue_stream(_stop_event(sse_factory))
        list(provider.grade_interview_response_stream(
            "Tell me about yourself", "I worked at Acme...", sample_profile,
            today="2026-01-01",
        ))
        payload = mock_openrouter.last_payload()
        assert payload["model"] == "F"
        assert payload["response_format"]["type"] == "json_schema"
        assert payload["response_format"]["json_schema"]["name"] == "grade_interview_output"


class TestChatInterview:
    def test_includes_history_in_messages(
            self, provider, mock_openrouter, sse_factory, sample_profile):
        mock_openrouter.queue_stream(_stop_event(sse_factory))
        history = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "system", "content": "ignored"},  # only user/assistant kept
            {"role": "user", "content": ""},  # empty content skipped
        ]
        list(provider.chat_interview_stream(
            history, sample_profile, today="2026-01-01",
        ))
        payload = mock_openrouter.last_payload()
        assert payload["model"] == "B"
        msgs = payload["messages"]
        # 1 system + 1 user-context + 2 history (user/assistant)
        assert len(msgs) == 4
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"
        assert msgs[2:] == [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]


class TestSummarizeInterviewNotes:
    def test_transcript_built_from_history(
            self, provider, mock_openrouter, sse_factory, sample_profile):
        mock_openrouter.queue_stream(_stop_event(sse_factory))
        list(provider.summarize_interview_notes_stream(
            history=[
                {"role": "user", "content": "q1"},
                {"role": "assistant", "content": "a1"},
            ],
            prior_notes="prev",
            profile=sample_profile,
            today="2026-01-01",
        ))
        user_msg = mock_openrouter.last_payload()["messages"][1]["content"]
        assert "user: q1" in user_msg
        assert "assistant: a1" in user_msg
        assert "<prior_notes>" in user_msg and "prev" in user_msg
