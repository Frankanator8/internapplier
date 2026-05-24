"""Tests for OpenRouterProvider._stream_chat_completion — the SSE parser
and request payload builder that all stream methods funnel through."""
from __future__ import annotations

import json

import pytest
import requests

from api.ai_provider.provider import OpenRouterProvider


@pytest.fixture
def provider(fake_api_key):
    return OpenRouterProvider()


def _drain(it):
    return list(it)


class TestMissingKey:
    def test_raises_value_error(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        p = OpenRouterProvider()
        with pytest.raises(ValueError, match="No API key"):
            list(p._stream_chat_completion(
                messages=[{"role": "user", "content": "hi"}],
                tier="basic", log_label="test",
            ))


class TestPlainStreaming:
    def test_yields_content_chunks_in_order(self, provider, mock_openrouter, sse_factory):
        events = [
            sse_factory.delta(content="Hello "),
            sse_factory.delta(content="world"),
            sse_factory.delta(finish_reason="stop"),
        ]
        mock_openrouter.queue_stream(events)
        out = _drain(provider._stream_chat_completion(
            messages=[{"role": "user", "content": "x"}],
            tier="basic", log_label="t",
        ))
        assert "".join(out) == "Hello world"

    def test_stops_on_done_marker(self, provider, mock_openrouter, sse_factory):
        # Manually craft lines so [DONE] terminates early
        lines = [
            f"data: {json.dumps(sse_factory.delta(content='A'))}",
            "data: [DONE]",
            f"data: {json.dumps(sse_factory.delta(content='B'))}",
        ]
        mock_openrouter.queue_raw(lines)
        out = _drain(provider._stream_chat_completion(
            messages=[{"role": "user", "content": "x"}],
            tier="basic", log_label="t",
        ))
        assert "".join(out) == "A"

    def test_ignores_comments_and_blanks(self, provider, mock_openrouter, sse_factory):
        lines = [
            "",
            ": keepalive",
            f"data: {json.dumps(sse_factory.delta(content='ok'))}",
            "data: [DONE]",
        ]
        mock_openrouter.queue_raw(lines)
        out = _drain(provider._stream_chat_completion(
            messages=[{"role": "u", "content": "x"}],
            tier="basic", log_label="t",
        ))
        assert "".join(out) == "ok"

    def test_skips_non_json_data_lines(self, provider, mock_openrouter, sse_factory):
        lines = [
            "data: garbage-not-json",
            f"data: {json.dumps(sse_factory.delta(content='hi'))}",
            "data: [DONE]",
        ]
        mock_openrouter.queue_raw(lines)
        out = _drain(provider._stream_chat_completion(
            messages=[{"role": "u", "content": "x"}],
            tier="basic", log_label="t",
        ))
        assert "".join(out) == "hi"

    def test_skips_choices_empty(self, provider, mock_openrouter):
        lines = [
            f"data: {json.dumps({'choices': []})}",
            f"data: {json.dumps({'choices': [{'delta': {'content': 'z'}}]})}",
            "data: [DONE]",
        ]
        mock_openrouter.queue_raw(lines)
        out = _drain(provider._stream_chat_completion(
            messages=[{"role": "u", "content": "x"}],
            tier="basic", log_label="t",
        ))
        assert "".join(out) == "z"


class TestRequestPayload:
    def test_payload_includes_model_and_messages(
            self, provider, mock_openrouter, sse_factory):
        mock_openrouter.queue_stream([sse_factory.delta(finish_reason="stop")])
        _drain(provider._stream_chat_completion(
            messages=[{"role": "user", "content": "hi"}],
            tier="basic", log_label="t",
        ))
        payload = mock_openrouter.last_payload()
        assert payload["stream"] is True
        assert payload["messages"] == [{"role": "user", "content": "hi"}]
        assert payload["model"]  # whatever tier maps to
        assert payload["usage"] == {"include": True}

    def test_response_format_only_when_provided(
            self, provider, mock_openrouter, sse_factory):
        mock_openrouter.queue_stream([sse_factory.delta(finish_reason="stop")])
        _drain(provider._stream_chat_completion(
            messages=[{"role": "u", "content": "x"}], tier="basic", log_label="t",
            response_format={"type": "json"},
        ))
        assert mock_openrouter.last_payload()["response_format"] == {"type": "json"}

    def test_sampling_keys_passed_through(
            self, provider, mock_openrouter, sse_factory):
        mock_openrouter.queue_stream([sse_factory.delta(finish_reason="stop")])
        _drain(provider._stream_chat_completion(
            messages=[{"role": "u", "content": "x"}], tier="basic", log_label="t",
            sampling={"temperature": 0.9, "top_p": None, "frequency_penalty": 0.4},
        ))
        payload = mock_openrouter.last_payload()
        assert payload["temperature"] == 0.9
        assert payload["frequency_penalty"] == 0.4
        # None values should be omitted
        assert "top_p" not in payload

    def test_no_tools_no_response_format_when_absent(
            self, provider, mock_openrouter, sse_factory):
        mock_openrouter.queue_stream([sse_factory.delta(finish_reason="stop")])
        _drain(provider._stream_chat_completion(
            messages=[{"role": "u", "content": "x"}], tier="basic", log_label="t",
        ))
        payload = mock_openrouter.last_payload()
        assert "tools" not in payload
        assert "response_format" not in payload
        assert "tool_choice" not in payload

    def test_authorization_header_uses_api_key(
            self, provider, mock_openrouter, sse_factory):
        mock_openrouter.queue_stream([sse_factory.delta(finish_reason="stop")])
        _drain(provider._stream_chat_completion(
            messages=[{"role": "u", "content": "x"}], tier="basic", log_label="t",
        ))
        headers = mock_openrouter.calls()[-1]["headers"]
        assert headers["Authorization"] == "Bearer test-key-abcdef"


class TestUsageRecording:
    def test_usage_block_triggers_record_usage(
            self, provider, mock_openrouter, sse_factory, mocker):
        rec = mocker.patch("api.ai_provider.http_client.record_usage")
        mock_openrouter.queue_stream([
            sse_factory.delta(content="x"),
            sse_factory.delta(usage={"prompt_tokens": 42, "completion_tokens": 7},
                              finish_reason="stop"),
        ])
        _drain(provider._stream_chat_completion(
            messages=[{"role": "u", "content": "y"}],
            tier="fast", log_label="t",
        ))
        rec.assert_called_once_with("fast", 42, 7)

    def test_missing_usage_logs_warning_no_raise(
            self, provider, mock_openrouter, sse_factory, mocker, caplog):
        rec = mocker.patch("api.ai_provider.http_client.record_usage")
        mock_openrouter.queue_stream([
            sse_factory.delta(content="x"),
            sse_factory.delta(finish_reason="stop"),
        ])
        out = _drain(provider._stream_chat_completion(
            messages=[{"role": "u", "content": "y"}],
            tier="basic", log_label="warn_test",
        ))
        assert "".join(out) == "x"
        rec.assert_not_called()


class TestErrors:
    def test_http_error_propagates(self, provider, mock_openrouter):
        mock_openrouter.queue_raw(["data: [DONE]"], status_code=500)
        with pytest.raises(requests.HTTPError):
            _drain(provider._stream_chat_completion(
                messages=[{"role": "u", "content": "x"}],
                tier="basic", log_label="t",
            ))


class TestModelTierMapping:
    def test_unknown_tier_falls_back_to_fast(
            self, provider, mock_openrouter, sse_factory, monkeypatch):
        # Force model config: basic -> "B", fast -> "F", powerful -> "P"
        monkeypatch.setattr(
            "api.ai_provider.http_client._load_model_config",
            lambda: {"basic": "B", "fast": "F", "powerful": "P"},
        )
        mock_openrouter.queue_stream([sse_factory.delta(finish_reason="stop")])
        _drain(provider._stream_chat_completion(
            messages=[{"role": "u", "content": "x"}],
            tier="banana", log_label="t",
        ))
        # Unknown tier defaults to the "fast" model
        assert mock_openrouter.last_payload()["model"] == "F"

    def test_known_tier_uses_mapped_model(
            self, provider, mock_openrouter, sse_factory, monkeypatch):
        monkeypatch.setattr(
            "api.ai_provider.http_client._load_model_config",
            lambda: {"basic": "B", "fast": "F", "powerful": "P"},
        )
        mock_openrouter.queue_stream([sse_factory.delta(finish_reason="stop")])
        _drain(provider._stream_chat_completion(
            messages=[{"role": "u", "content": "x"}],
            tier="powerful", log_label="t",
        ))
        assert mock_openrouter.last_payload()["model"] == "P"
