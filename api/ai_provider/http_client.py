"""HTTP transport + OpenAI-style tool-loop for OpenRouter chat completions.

This module owns everything provider-agnostic about the wire protocol:
constructing the request payload, streaming SSE chunks, accumulating
tool-call deltas, dispatching tool handlers, and re-issuing the request
until the model returns a normal stop. Domain-specific prompts and
completions live in :mod:`api.ai_provider.provider`.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Iterator

import requests

from .formatting import TOOL_EVENT_PREFIX, _format_tool_event
from .settings import _load_model_config
from ..token_usage import record_usage

logger = logging.getLogger(__name__)

BASE_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterHTTPClient:
    """Owns the OpenRouter HTTP connection + the tool-calling loop.

    Domain methods on :class:`OpenRouterProvider` build messages and hand
    them to :meth:`stream_chat_completion` or :meth:`post_json`.
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        key_hint = (
            f"...{self.api_key[-6:]}" if len(self.api_key) >= 6
            else ("(set)" if self.api_key else "(MISSING)")
        )
        logger.debug("OpenRouterHTTPClient init — api_key=%s", key_hint)

    # ── Internals ───────────────────────────────────────────────────────────

    def _model_for(self, tier: str) -> str:
        config = _load_model_config()
        return config.get(tier) or config["fast"]

    def _require_api_key(self, log_label: str) -> None:
        if not self.api_key:
            logger.error("%s — API key missing", log_label)
            raise ValueError(
                "No API key found. Set the OPENROUTER_API_KEY environment variable."
            )

    def _headers(self, *, sse: bool) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if sse:
            headers["Accept"] = "text/event-stream"
        return headers

    def _record_token_usage(
        self, log_label: str, tier: str, usage: dict | None, *, model: str
    ) -> None:
        if not isinstance(usage, dict):
            logger.warning("%s — no usage block received (model=%s)", log_label, model)
            return
        prompt_t = usage.get("prompt_tokens", 0)
        completion_t = usage.get("completion_tokens", 0)
        cache_read = (
            usage.get("cache_read_input_tokens")
            or (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
            or 0
        )
        cache_write = usage.get("cache_creation_input_tokens", 0)
        logger.info(
            "%s — usage tier=%s prompt=%s completion=%s cache_read=%s cache_write=%s",
            log_label, tier, prompt_t, completion_t, cache_read, cache_write,
        )
        try:
            record_usage(tier, prompt_t, completion_t)
        except Exception:
            logger.exception("%s — record_usage failed", log_label)

    @staticmethod
    def _build_stream_payload(
        *,
        model: str,
        messages: list[dict],
        tools: list[dict] | None,
        tool_choice_auto: bool,
        response_format: dict | None,
        sampling: dict | None,
    ) -> dict:
        payload: dict = {
            "model": model,
            "stream": True,
            "messages": messages,
            "usage": {"include": True},
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto" if tool_choice_auto else "none"
        if response_format:
            payload["response_format"] = response_format
        if sampling:
            for k, v in sampling.items():
                if v is not None:
                    payload[k] = v
        return payload

    @staticmethod
    def _assemble_tool_calls(tool_calls_acc: dict[int, dict]) -> list[dict]:
        return [
            {
                "id": tool_calls_acc[idx]["id"] or f"call_{idx}",
                "type": "function",
                "function": {
                    "name": tool_calls_acc[idx]["name"] or "",
                    "arguments": tool_calls_acc[idx]["arguments"] or "{}",
                },
            }
            for idx in sorted(tool_calls_acc)
        ]

    def _dispatch_tool_call(
        self,
        tc: dict,
        *,
        tool_overrides: dict | None,
        handlers: dict,
        log_label: str,
        round_idx: int,
    ) -> tuple[dict, str]:
        name = tc["function"]["name"]
        args_raw = tc["function"]["arguments"]
        args: dict = {}
        try:
            parsed = json.loads(args_raw) if args_raw else {}
            if not isinstance(parsed, dict):
                raise ValueError("arguments must decode to a JSON object")
            args = parsed
        except (json.JSONDecodeError, ValueError) as e:
            result = {"ok": False, "error": f"invalid arguments: {e}"}
        else:
            handler = (tool_overrides or {}).get(name) or handlers.get(name)
            if handler is None:
                result = {"ok": False, "error": f"unknown tool: {name}"}
            else:
                try:
                    result = handler(**args)
                except TypeError as e:
                    result = {"ok": False, "error": f"bad arguments: {e}"}
                except Exception as e:
                    logger.exception("%s — tool %s raised", log_label, name)
                    result = {"ok": False, "error": str(e)}

        try:
            args_preview = json.dumps(args)[:500]
        except Exception:
            args_preview = repr(args)[:500]
        try:
            result_preview = json.dumps(result)[:500]
        except Exception:
            result_preview = repr(result)[:500]
        logger.info(
            "%s — tool %s round=%d ok=%s args=%s result=%s",
            log_label, name, round_idx, result.get("ok"),
            args_preview, result_preview,
        )
        return result, _format_tool_event(name, round_idx, args, result)

    def _stream_round(
        self,
        payload: dict,
        *,
        tier: str,
        model: str,
        log_label: str,
        timeout: tuple[float, float],
        emit_content: bool,
    ) -> Iterator[str]:
        """Stream a single completion request. Yields content chunks when
        ``emit_content`` is True. Returns ``(content, tool_calls, finish, usage)``
        via ``StopIteration.value`` (i.e. ``return`` from this generator)."""
        accumulated: list[str] = []
        tool_calls_acc: dict[int, dict] = {}
        finish_reason: str | None = None
        final_usage: dict | None = None
        chunk_count = 0
        t0 = time.perf_counter()
        try:
            with requests.post(
                BASE_URL,
                headers=self._headers(sse=True),
                json=payload,
                stream=True,
                timeout=timeout,
            ) as response:
                response.raise_for_status()
                response.encoding = "utf-8"
                for line in response.iter_lines(decode_unicode=True):
                    if not line or line.startswith(": ") or not line.startswith("data: "):
                        continue
                    raw = line[6:].strip()
                    if raw == "[DONE]":
                        break
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        logger.debug("%s — skipping non-JSON line: %r", log_label, raw[:120])
                        continue
                    if isinstance(data.get("usage"), dict):
                        final_usage = data["usage"]
                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    choice = choices[0]
                    delta = choice.get("delta") or {}
                    content = delta.get("content")
                    if content:
                        chunk_count += 1
                        accumulated.append(content)
                        if emit_content:
                            yield content
                    for tc in delta.get("tool_calls") or []:
                        idx = tc.get("index", 0)
                        entry = tool_calls_acc.setdefault(
                            idx, {"id": None, "name": None, "arguments": ""},
                        )
                        if tc.get("id"):
                            entry["id"] = tc["id"]
                        fn = tc.get("function") or {}
                        if fn.get("name"):
                            entry["name"] = fn["name"]
                        if fn.get("arguments"):
                            entry["arguments"] += fn["arguments"]
                    if choice.get("finish_reason"):
                        finish_reason = choice["finish_reason"]
            logger.info(
                "%s — stream done in %.2fs, %d chunks, finish=%s, tool_calls=%d",
                log_label, time.perf_counter() - t0, chunk_count, finish_reason,
                len(tool_calls_acc),
            )
            self._record_token_usage(log_label, tier, final_usage, model=model)
        except Exception:
            logger.exception("%s — stream failed", log_label)
            raise

        return "".join(accumulated), tool_calls_acc, finish_reason, final_usage

    # ── Public entry points ─────────────────────────────────────────────────

    def stream_chat_completion(
        self,
        messages: list[dict],
        *,
        tier: str,
        log_label: str,
        timeout: tuple[float, float] = (10.0, 30.0),
        tools: list[dict] | None = None,
        max_tool_rounds: int = 4,
        tool_overrides: dict | None = None,
        response_format: dict | None = None,
        sampling: dict | None = None,
    ) -> Iterator[str]:
        """SSE-stream chat completions, yielding incremental content chunks.

        When ``tools`` is provided, runs an OpenAI-style tool-calling loop:
        accumulates streamed ``tool_calls``, dispatches them against
        :data:`agent_tools.TOOL_HANDLERS`, appends the assistant + tool
        messages, and re-issues the request until the model finishes with
        a normal stop or ``max_tool_rounds`` is reached.

        Tool-call activity is surfaced as out-of-band chunks prefixed with
        :data:`TOOL_EVENT_PREFIX`; downstream collectors strip these so they
        do not pollute the model's text output.
        """
        self._require_api_key(log_label)

        from ..generate_resume.agent_tools import TOOL_HANDLERS

        model = self._model_for(tier)
        logger.debug(
            "%s — POST %s tier=%s model=%s stream=True timeout=%s tools=%s",
            log_label, BASE_URL, tier, model, timeout,
            [t["function"]["name"] for t in tools] if tools else None,
        )

        messages = list(messages)
        rounds_used = 0

        while True:
            payload = self._build_stream_payload(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice_auto=rounds_used < max_tool_rounds,
                response_format=response_format,
                sampling=sampling,
            )
            content, tool_calls, finish_reason, usage = yield from self._stream_round(
                payload, tier=tier, model=model, log_label=log_label, timeout=timeout,
                emit_content=not tools,
            )

            if finish_reason != "tool_calls" or not tool_calls:
                if content and tools:
                    yield content
                return

            if content.strip():
                yield TOOL_EVENT_PREFIX + (
                    f"[reasoning] round {rounds_used + 1}:\n{content}\n"
                )

            rounds_used += 1
            assembled = self._assemble_tool_calls(tool_calls)
            messages.append({
                "role": "assistant",
                "content": content or None,
                "tool_calls": assembled,
            })

            for tc in assembled:
                result, event = self._dispatch_tool_call(
                    tc, tool_overrides=tool_overrides,
                    handlers=TOOL_HANDLERS, log_label=log_label, round_idx=rounds_used,
                )
                yield TOOL_EVENT_PREFIX + event
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result),
                })

    def post_json(
        self,
        *,
        messages: list[dict],
        tier: str,
        log_label: str,
        response_format: dict | None = None,
        timeout: float | tuple[float, float] = 60,
    ) -> str:
        """POST a non-streaming completion. Returns the assistant's content
        string; logs and records token usage as a side effect."""
        self._require_api_key(log_label)
        model = self._model_for(tier)
        logger.debug(
            "%s — POST %s tier=%s model=%s timeout=%s",
            log_label, BASE_URL, tier, model, timeout,
        )
        payload: dict = {"model": model, "messages": messages}
        if response_format:
            payload["response_format"] = response_format

        t0 = time.perf_counter()
        try:
            response = requests.post(
                BASE_URL,
                headers=self._headers(sse=False),
                json=payload,
                timeout=timeout,
            )
            logger.info(
                "%s — HTTP %s in %.2fs",
                log_label, response.status_code, time.perf_counter() - t0,
            )
            logger.debug("%s — raw response: %s", log_label, response.text[:300])
            response.raise_for_status()
        except Exception:
            logger.exception("%s — request failed", log_label)
            raise

        response_json = response.json()
        self._record_token_usage(
            log_label, tier,
            response_json.get("usage") if isinstance(response_json, dict) else None,
            model=model,
        )
        return response_json["choices"][0]["message"]["content"].strip()
