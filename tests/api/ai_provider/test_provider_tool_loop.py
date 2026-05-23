"""Tests for the OpenAI-style tool-calling loop inside
``OpenRouterProvider._stream_chat_completion``."""
from __future__ import annotations

import json

import pytest

from api.ai_provider.formatting import TOOL_EVENT_PREFIX
from api.ai_provider.provider import OpenRouterProvider


@pytest.fixture
def provider(fake_api_key):
    return OpenRouterProvider()


def _drain(it):
    return list(it)


def _tool_call_event(idx: int, call_id: str | None, name: str | None,
                     arguments: str) -> dict:
    fn: dict = {}
    if name is not None:
        fn["name"] = name
    if arguments:
        fn["arguments"] = arguments
    tc: dict = {"index": idx, "function": fn}
    if call_id is not None:
        tc["id"] = call_id
    return tc


def _make_tools():
    return [{
        "type": "function",
        "function": {
            "name": "echo",
            "description": "Echo back the input",
            "parameters": {"type": "object", "properties": {"x": {"type": "string"}}},
        },
    }]


class TestSingleToolCallRound:
    def test_handler_invoked_with_parsed_args(
            self, provider, mock_openrouter, sse_factory):
        # Round 1: tool_call requesting echo({"x": "hi"})
        mock_openrouter.queue_stream([
            sse_factory.delta(tool_calls=[
                _tool_call_event(0, "call_1", "echo", '{"x": "hi"}')
            ]),
            sse_factory.delta(finish_reason="tool_calls"),
        ])
        # Round 2: model responds with content + stop
        mock_openrouter.queue_stream([
            sse_factory.delta(content="done"),
            sse_factory.delta(finish_reason="stop"),
        ])

        captured = {}

        def handler(**kwargs):
            captured.update(kwargs)
            return {"ok": True, "echoed": kwargs["x"]}

        out = _drain(provider._stream_chat_completion(
            messages=[{"role": "user", "content": "go"}],
            tier="powerful", log_label="t",
            tools=_make_tools(),
            tool_overrides={"echo": handler},
        ))
        assert captured == {"x": "hi"}
        # Final content is yielded after tool loop
        text_chunks = [c for c in out if not c.startswith(TOOL_EVENT_PREFIX)]
        assert "".join(text_chunks) == "done"

    def test_tool_event_emitted_with_prefix(
            self, provider, mock_openrouter, sse_factory):
        mock_openrouter.queue_stream([
            sse_factory.delta(tool_calls=[
                _tool_call_event(0, "c1", "echo", '{"x":"v"}')]),
            sse_factory.delta(finish_reason="tool_calls"),
        ])
        mock_openrouter.queue_stream([
            sse_factory.delta(content="ok"),
            sse_factory.delta(finish_reason="stop"),
        ])
        out = _drain(provider._stream_chat_completion(
            messages=[{"role": "user", "content": "go"}],
            tier="powerful", log_label="t",
            tools=_make_tools(),
            tool_overrides={"echo": lambda **kw: {"ok": True}},
        ))
        tool_events = [c for c in out if c.startswith(TOOL_EVENT_PREFIX)]
        assert any("echo" in e for e in tool_events)

    def test_tool_message_appended_with_call_id(
            self, provider, mock_openrouter, sse_factory):
        mock_openrouter.queue_stream([
            sse_factory.delta(tool_calls=[
                _tool_call_event(0, "call_xyz", "echo", '{"x":"v"}')]),
            sse_factory.delta(finish_reason="tool_calls"),
        ])
        mock_openrouter.queue_stream([
            sse_factory.delta(finish_reason="stop"),
        ])
        _drain(provider._stream_chat_completion(
            messages=[{"role": "user", "content": "go"}],
            tier="powerful", log_label="t",
            tools=_make_tools(),
            tool_overrides={"echo": lambda **kw: {"ok": True, "v": "x"}},
        ))
        # The 2nd request payload should include the tool message
        second_msgs = mock_openrouter.calls()[1]["json"]["messages"]
        tool_msgs = [m for m in second_msgs if m["role"] == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0]["tool_call_id"] == "call_xyz"
        assert json.loads(tool_msgs[0]["content"]) == {"ok": True, "v": "x"}


class TestArgAccumulation:
    def test_streamed_argument_fragments_concatenated(
            self, provider, mock_openrouter, sse_factory):
        # Function name in first chunk, args split across multiple deltas
        mock_openrouter.queue_stream([
            sse_factory.delta(tool_calls=[
                _tool_call_event(0, "c1", "echo", '{"x"')]),
            sse_factory.delta(tool_calls=[
                _tool_call_event(0, None, None, ':"hello')]),
            sse_factory.delta(tool_calls=[
                _tool_call_event(0, None, None, '"}')]),
            sse_factory.delta(finish_reason="tool_calls"),
        ])
        mock_openrouter.queue_stream([sse_factory.delta(finish_reason="stop")])
        captured = {}
        _drain(provider._stream_chat_completion(
            messages=[{"role": "user", "content": "go"}],
            tier="powerful", log_label="t",
            tools=_make_tools(),
            tool_overrides={"echo": lambda **kw: captured.update(kw) or {"ok": True}},
        ))
        assert captured == {"x": "hello"}


class TestErrorHandling:
    def test_invalid_json_args_returns_error_envelope(
            self, provider, mock_openrouter, sse_factory):
        mock_openrouter.queue_stream([
            sse_factory.delta(tool_calls=[
                _tool_call_event(0, "c1", "echo", "{not json")]),
            sse_factory.delta(finish_reason="tool_calls"),
        ])
        mock_openrouter.queue_stream([sse_factory.delta(finish_reason="stop")])

        invoked = []
        _drain(provider._stream_chat_completion(
            messages=[{"role": "u", "content": "x"}],
            tier="powerful", log_label="t",
            tools=_make_tools(),
            tool_overrides={"echo": lambda **kw: invoked.append(kw) or {"ok": True}},
        ))
        assert invoked == []  # handler never called
        tool_content = json.loads(mock_openrouter.calls()[1]["json"]["messages"][-1]["content"])
        assert tool_content["ok"] is False
        assert "invalid arguments" in tool_content["error"]

    def test_unknown_tool_name_returns_error(
            self, provider, mock_openrouter, sse_factory):
        mock_openrouter.queue_stream([
            sse_factory.delta(tool_calls=[
                _tool_call_event(0, "c1", "ghost", "{}")]),
            sse_factory.delta(finish_reason="tool_calls"),
        ])
        mock_openrouter.queue_stream([sse_factory.delta(finish_reason="stop")])
        _drain(provider._stream_chat_completion(
            messages=[{"role": "u", "content": "x"}],
            tier="powerful", log_label="t",
            tools=_make_tools(),
            tool_overrides={},  # no handler for "ghost"
        ))
        tool_content = json.loads(mock_openrouter.calls()[1]["json"]["messages"][-1]["content"])
        assert tool_content["ok"] is False
        assert "unknown tool: ghost" in tool_content["error"]

    def test_handler_typeerror_distinct_from_other_exceptions(
            self, provider, mock_openrouter, sse_factory):
        def bad_args_handler(**kw):
            raise TypeError("got an unexpected keyword")

        mock_openrouter.queue_stream([
            sse_factory.delta(tool_calls=[
                _tool_call_event(0, "c1", "echo", '{"weird": 1}')]),
            sse_factory.delta(finish_reason="tool_calls"),
        ])
        mock_openrouter.queue_stream([sse_factory.delta(finish_reason="stop")])
        _drain(provider._stream_chat_completion(
            messages=[{"role": "u", "content": "x"}],
            tier="powerful", log_label="t",
            tools=_make_tools(),
            tool_overrides={"echo": bad_args_handler},
        ))
        content = json.loads(mock_openrouter.calls()[1]["json"]["messages"][-1]["content"])
        assert content == {"ok": False, "error": "bad arguments: got an unexpected keyword"}

    def test_handler_generic_exception_captured(
            self, provider, mock_openrouter, sse_factory):
        def boom(**kw):
            raise RuntimeError("kaboom")

        mock_openrouter.queue_stream([
            sse_factory.delta(tool_calls=[
                _tool_call_event(0, "c1", "echo", "{}")]),
            sse_factory.delta(finish_reason="tool_calls"),
        ])
        mock_openrouter.queue_stream([sse_factory.delta(finish_reason="stop")])
        _drain(provider._stream_chat_completion(
            messages=[{"role": "u", "content": "x"}],
            tier="powerful", log_label="t",
            tools=_make_tools(),
            tool_overrides={"echo": boom},
        ))
        content = json.loads(mock_openrouter.calls()[1]["json"]["messages"][-1]["content"])
        assert content == {"ok": False, "error": "kaboom"}


class TestToolChoiceAfterMaxRounds:
    def test_tool_choice_auto_for_first_rounds_then_none(
            self, provider, mock_openrouter, sse_factory):
        # Loop will run until max_tool_rounds is exhausted
        for _ in range(3):
            mock_openrouter.queue_stream([
                sse_factory.delta(tool_calls=[
                    _tool_call_event(0, "c1", "echo", "{}")]),
                sse_factory.delta(finish_reason="tool_calls"),
            ])
        # Final response with no tool calls
        mock_openrouter.queue_stream([sse_factory.delta(finish_reason="stop")])

        _drain(provider._stream_chat_completion(
            messages=[{"role": "u", "content": "x"}],
            tier="powerful", log_label="t",
            tools=_make_tools(),
            max_tool_rounds=2,
            tool_overrides={"echo": lambda **kw: {"ok": True}},
        ))
        payloads = [c["json"] for c in mock_openrouter.calls()]
        # Round 0: tool_choice auto. After 2 tool rounds executed, next call sets "none"
        assert payloads[0]["tool_choice"] == "auto"
        assert payloads[1]["tool_choice"] == "auto"
        assert payloads[2]["tool_choice"] == "none"


class TestToolOverridesPrecedence:
    def test_override_wins_over_global_handler(
            self, provider, mock_openrouter, sse_factory, monkeypatch):
        from api.generate_resume import agent_tools

        called = {"global": False, "override": False}

        def global_h(**kw):
            called["global"] = True
            return {"ok": True}

        def override_h(**kw):
            called["override"] = True
            return {"ok": True}

        monkeypatch.setitem(agent_tools.TOOL_HANDLERS, "echo", global_h)
        mock_openrouter.queue_stream([
            sse_factory.delta(tool_calls=[
                _tool_call_event(0, "c1", "echo", "{}")]),
            sse_factory.delta(finish_reason="tool_calls"),
        ])
        mock_openrouter.queue_stream([sse_factory.delta(finish_reason="stop")])
        _drain(provider._stream_chat_completion(
            messages=[{"role": "u", "content": "x"}],
            tier="powerful", log_label="t",
            tools=_make_tools(),
            tool_overrides={"echo": override_h},
        ))
        assert called == {"global": False, "override": True}


class TestContentBufferingWhenTools:
    def test_content_not_yielded_mid_tool_loop_but_at_end(
            self, provider, mock_openrouter, sse_factory):
        # First round: streaming content but no tool calls -> finishes
        mock_openrouter.queue_stream([
            sse_factory.delta(content="hello"),
            sse_factory.delta(content=" world"),
            sse_factory.delta(finish_reason="stop"),
        ])
        out = _drain(provider._stream_chat_completion(
            messages=[{"role": "u", "content": "x"}],
            tier="powerful", log_label="t",
            tools=_make_tools(),
            tool_overrides={"echo": lambda **kw: {"ok": True}},
        ))
        text = "".join(c for c in out if not c.startswith(TOOL_EVENT_PREFIX))
        assert text == "hello world"
