import datetime
import json
import logging
import os
import time
from typing import Iterator

import requests

from .formatting import (
    TOOL_EVENT_PREFIX,
    _format_context,
    _format_tool_event,
    _profile_json,
)
from .prompts import load_prompt, load_schema
from .settings import _load_model_config, get_resume_template

logger = logging.getLogger(__name__)


class OpenRouterProvider:
    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(
        self,
        api_key: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        key_hint = f"...{self.api_key[-6:]}" if len(self.api_key) >= 6 else ("(set)" if self.api_key else "(MISSING)")
        logger.debug("OpenRouterProvider init — api_key=%s", key_hint)

    def _model_for(self, tier: str) -> str:
        config = _load_model_config()
        return config.get(tier) or config["fast"]

    def analyze_bullet_stream(self, bullet: str, context: dict) -> Iterator[str]:
        logger.info("analyze_bullet_stream — bullet=%r context=%s", bullet[:120], context)
        user_message = (
            f"{_format_context(context)}\n\n"
            f'Resume bullet: "{bullet}"\n\n'
            "Please provide:\n"
            "1. CRITIQUE: A 1-2 sentence assessment of this bullet's weaknesses "
            "(e.g., missing metrics, weak action verb, unclear impact).\n"
            "2. REWRITE A: An improved version of this bullet.\n"
            "3. REWRITE B: A second, alternative improved version."
        )
        yield from self._stream_chat_completion(
            messages=[
                {"role": "system", "content": load_prompt("analyze_bullet.txt")},
                {"role": "user", "content": user_message},
            ],
            tier="basic",
            log_label="analyze_bullet_stream",
            timeout=(10.0, 60.0),
        )

    def _stream_chat_completion(
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
        if not self.api_key:
            logger.error("%s — API key missing", log_label)
            raise ValueError(
                "No API key found. Set the OPENROUTER_API_KEY environment variable."
            )

        from ..generate_resume.agent_tools import TOOL_HANDLERS

        model = self._model_for(tier)
        logger.debug("%s — POST %s tier=%s model=%s stream=True timeout=%s tools=%s",
                     log_label, self.BASE_URL, tier, model, timeout,
                     [t["function"]["name"] for t in tools] if tools else None)

        messages = list(messages)
        rounds_used = 0

        while True:
            payload_json: dict = {
                "model": model,
                "stream": True,
                "messages": messages,
            }
            if tools:
                payload_json["tools"] = tools
                payload_json["tool_choice"] = (
                    "none" if rounds_used >= max_tool_rounds else "auto"
                )
            if response_format:
                payload_json["response_format"] = response_format

            accumulated_content: list[str] = []
            tool_calls_acc: dict[int, dict] = {}
            finish_reason: str | None = None
            t0 = time.perf_counter()
            chunk_count = 0
            try:
                with requests.post(
                    self.BASE_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "Accept": "text/event-stream",
                    },
                    json=payload_json,
                    stream=True,
                    timeout=timeout,
                ) as response:
                    response.raise_for_status()
                    response.encoding = "utf-8"
                    for line in response.iter_lines(decode_unicode=True):
                        if not line or line.startswith(": ") or not line.startswith("data: "):
                            continue
                        payload = line[6:].strip()
                        if payload == "[DONE]":
                            break
                        try:
                            data = json.loads(payload)
                        except json.JSONDecodeError:
                            logger.debug("%s — skipping non-JSON line: %r",
                                         log_label, payload[:120])
                            continue
                        choices = data.get("choices") or []
                        if not choices:
                            continue
                        choice = choices[0]
                        delta = choice.get("delta") or {}
                        content = delta.get("content")
                        if content:
                            chunk_count += 1
                            accumulated_content.append(content)
                            if not tools:
                                yield content
                        for tc in delta.get("tool_calls") or []:
                            idx = tc.get("index", 0)
                            entry = tool_calls_acc.setdefault(
                                idx, {"id": None, "name": None, "arguments": ""}
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
                elapsed = time.perf_counter() - t0
                logger.info(
                    "%s — stream done in %.2fs, %d chunks, finish=%s, tool_calls=%d",
                    log_label, elapsed, chunk_count, finish_reason,
                    len(tool_calls_acc),
                )
            except Exception:
                logger.exception("%s — stream failed", log_label)
                raise

            round_content = "".join(accumulated_content)

            if finish_reason != "tool_calls" or not tool_calls_acc:
                if round_content and tools:
                    yield round_content
                return

            if round_content.strip():
                yield TOOL_EVENT_PREFIX + (
                    f"[reasoning] round {rounds_used + 1}:\n{round_content}\n"
                )

            rounds_used += 1
            assembled: list[dict] = []
            for idx in sorted(tool_calls_acc):
                entry = tool_calls_acc[idx]
                assembled.append({
                    "id": entry["id"] or f"call_{idx}",
                    "type": "function",
                    "function": {
                        "name": entry["name"] or "",
                        "arguments": entry["arguments"] or "{}",
                    },
                })

            messages.append({
                "role": "assistant",
                "content": "".join(accumulated_content) or None,
                "tool_calls": assembled,
            })

            for tc in assembled:
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
                    handler = (tool_overrides or {}).get(name) or TOOL_HANDLERS.get(name)
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

                logger.info(
                    "%s — tool %s round=%d ok=%s",
                    log_label, name, rounds_used, result.get("ok"),
                )
                yield TOOL_EVENT_PREFIX + _format_tool_event(
                    name, rounds_used, args, result
                )

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result),
                })

    def grade_resume_stream(
        self,
        latex: str,
        job_description: str,
        *,
        over_by: float = 0.0,
        today: str | None = None,
        company_research: dict | None = None,
        profile: dict | None = None,
    ) -> Iterator[str]:
        profile_summary = (
            ", ".join(
                f"{k}={len(profile.get(k, []))}"
                for k in ("experience", "projects", "education", "awards", "skills", "hobbies")
            )
            if profile else "none"
        )
        logger.info(
            "grade_resume_stream — jd=%r latex_chars=%d over_by=%.3f research=%s profile=%s",
            job_description[:120], len(latex), over_by,
            f"{len(company_research)} keys" if company_research else "none",
            profile_summary,
        )
        today = today or datetime.date.today().isoformat()
        page_status = (
            f"<page_status>over by {over_by:.2f} page(s) — emit drops</page_status>\n\n"
            if over_by > 1e-6 else ""
        )
        research_block = (
            f"<company_research>\n{json.dumps(company_research, indent=2)}\n</company_research>\n\n"
            if company_research else ""
        )
        profile_block = (
            f"<profile>\n{_profile_json(profile)}\n</profile>\n\n" if profile else ""
        )
        user_message = (
            f"<today>{today}</today>\n\n"
            f"{page_status}"
            f"{profile_block}"
            f"{research_block}"
            f"Job Description:\n{job_description}\n\n"
            f"Resume LaTeX:\n{latex}\n\n"
            "Grade this resume against the job description following the system "
            "instructions exactly."
        )
        from ..generate_resume.agent_tools import OPENAI_TOOL_SCHEMAS

        yield from self._stream_chat_completion(
            messages=[
                {"role": "system", "content": load_prompt("grade_resume.txt")},
                {"role": "user", "content": user_message},
            ],
            tier="powerful",
            log_label="grade_resume",
            tools=[OPENAI_TOOL_SCHEMAS["page_length"]],
        )

    def _build_generate_resume_messages(
        self,
        profile: dict,
        job_description: str,
        feedback: str | None,
        previous_latex: str | None = None,
        today: str | None = None,
        company_research: dict | None = None,
    ) -> list[dict]:
        today = today or datetime.date.today().isoformat()
        sections: list[str] = [
            f"<today>{today}</today>",
            f"<job_description>\n{job_description}\n</job_description>",
            f"<profile>\n{_profile_json(profile)}\n</profile>",
        ]
        template = get_resume_template().strip()
        if template:
            sections.append(f"<template>\n{template}\n</template>")
        if previous_latex:
            sections.append(f"<previous_draft>\n{previous_latex}\n</previous_draft>")
        if feedback:
            sections.append(f"<feedback>\n{feedback}\n</feedback>")
        if company_research:
            sections.append(
                f"<company_research>\n{json.dumps(company_research, indent=2)}\n</company_research>"
            )

        return [
            {"role": "system", "content": load_prompt("generate_resume.txt")},
            {"role": "user", "content": "\n\n".join(sections)},
        ]

    def generate_resume_stream(
        self,
        profile: dict,
        job_description: str,
        feedback: str | None = None,
        previous_latex: str | None = None,
        today: str | None = None,
        company_research: dict | None = None,
    ) -> Iterator[str]:
        logger.info(
            "generate_resume_stream — jd=%r feedback=%s previous_latex=%s research=%s",
            job_description[:120],
            f"{len(feedback)} chars" if feedback else "none",
            f"{len(previous_latex)} chars" if previous_latex else "none",
            f"{len(company_research)} keys" if company_research else "none",
        )
        from ..generate_resume.agent_tools import OPENAI_TOOL_SCHEMAS

        messages = self._build_generate_resume_messages(
            profile, job_description, feedback, previous_latex, today,
            company_research=company_research,
        )
        yield from self._stream_chat_completion(
            messages=messages,
            tier="powerful",
            log_label="generate_resume",
            tools=[OPENAI_TOOL_SCHEMAS["page_length"]],
        )

    def answer_question_stream(
        self,
        question: str,
        profile: dict,
        company_research: dict | None = None,
        company_name: str | None = None,
        job_description: str | None = None,
        today: str | None = None,
    ) -> Iterator[str]:
        logger.info(
            "answer_question_stream — question=%r company=%r research=%s jd=%s",
            question[:120],
            company_name,
            f"{len(company_research)} keys" if company_research else "none",
            f"{len(job_description)} chars" if job_description else "none",
        )
        today = today or datetime.date.today().isoformat()
        sections: list[str] = [
            f"<today>{today}</today>",
            f"<question>\n{question}\n</question>",
        ]
        if company_name:
            sections.append(f"<company_name>{company_name}</company_name>")
        sections.append(f"<profile>\n{_profile_json(profile)}\n</profile>")
        if company_research:
            sections.append(
                f"<company_research>\n{json.dumps(company_research, indent=2)}\n</company_research>"
            )
        if job_description:
            sections.append(f"<job_description>\n{job_description}\n</job_description>")

        yield from self._stream_chat_completion(
            messages=[
                {"role": "system", "content": load_prompt("answer_question.txt")},
                {"role": "user", "content": "\n\n".join(sections)},
            ],
            tier="basic",
            log_label="answer_question",
        )

    def grade_interview_response_stream(
        self,
        question: str,
        response: str,
        profile: dict,
        company_research: dict | None = None,
        company_name: str | None = None,
        job_description: str | None = None,
        today: str | None = None,
    ) -> Iterator[str]:
        logger.info(
            "grade_interview_response_stream — question=%r response_chars=%d company=%r research=%s jd=%s",
            question[:120],
            len(response),
            company_name,
            f"{len(company_research)} keys" if company_research else "none",
            f"{len(job_description)} chars" if job_description else "none",
        )
        today = today or datetime.date.today().isoformat()
        sections: list[str] = [
            f"<today>{today}</today>",
            f"<question>\n{question}\n</question>",
            f"<response>\n{response}\n</response>",
        ]
        if company_name:
            sections.append(f"<company_name>{company_name}</company_name>")
        sections.append(f"<profile>\n{_profile_json(profile)}\n</profile>")
        if company_research:
            sections.append(
                f"<company_research>\n{json.dumps(company_research, indent=2)}\n</company_research>"
            )
        if job_description:
            sections.append(f"<job_description>\n{job_description}\n</job_description>")

        yield from self._stream_chat_completion(
            messages=[
                {"role": "system", "content": load_prompt("grade_interview.txt")},
                {"role": "user", "content": "\n\n".join(sections)},
            ],
            tier="fast",
            log_label="grade_interview_response",
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "grade_interview_output",
                    "strict": True,
                    "schema": load_schema("grade_interview.schema.json"),
                },
            },
        )

    def chat_interview_stream(
        self,
        history: list[dict],
        profile: dict,
        company_name: str | None = None,
        company_research: dict | None = None,
        job_description: str | None = None,
        today: str | None = None,
    ) -> Iterator[str]:
        logger.info(
            "chat_interview_stream — turns=%d company=%r research=%s jd=%s",
            len(history),
            company_name,
            f"{len(company_research)} keys" if company_research else "none",
            f"{len(job_description)} chars" if job_description else "none",
        )
        today = today or datetime.date.today().isoformat()
        context_sections: list[str] = [f"<today>{today}</today>"]
        if company_name:
            context_sections.append(f"<company_name>{company_name}</company_name>")
        context_sections.append(f"<profile>\n{_profile_json(profile)}\n</profile>")
        if company_research:
            context_sections.append(
                f"<company_research>\n{json.dumps(company_research, indent=2)}\n</company_research>"
            )
        if job_description:
            context_sections.append(f"<job_description>\n{job_description}\n</job_description>")

        messages: list[dict] = [
            {"role": "system", "content": load_prompt("interview_chat.txt")},
            {"role": "user", "content": "\n\n".join(context_sections)},
        ]
        for turn in history:
            role = turn.get("role")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        yield from self._stream_chat_completion(
            messages=messages,
            tier="basic",
            log_label="chat_interview",
        )

    def summarize_interview_notes_stream(
        self,
        history: list[dict],
        prior_notes: str,
        profile: dict,
        company_name: str | None = None,
        company_research: dict | None = None,
        job_description: str | None = None,
        today: str | None = None,
    ) -> Iterator[str]:
        logger.info(
            "summarize_interview_notes_stream — turns=%d prior_chars=%d company=%r",
            len(history), len(prior_notes or ""), company_name,
        )
        today = today or datetime.date.today().isoformat()
        transcript_lines: list[str] = []
        for turn in history:
            role = turn.get("role")
            content = (turn.get("content") or "").strip()
            if role in ("user", "assistant") and content:
                transcript_lines.append(f"{role}: {content}")
        transcript_text = "\n\n".join(transcript_lines)

        sections: list[str] = [
            f"<today>{today}</today>",
            f"<prior_notes>\n{prior_notes or ''}\n</prior_notes>",
            f"<transcript>\n{transcript_text}\n</transcript>",
            f"<profile>\n{_profile_json(profile)}\n</profile>",
        ]
        if company_name:
            sections.append(f"<company_name>{company_name}</company_name>")
        if company_research:
            sections.append(
                f"<company_research>\n{json.dumps(company_research, indent=2)}\n</company_research>"
            )
        if job_description:
            sections.append(f"<job_description>\n{job_description}\n</job_description>")

        yield from self._stream_chat_completion(
            messages=[
                {"role": "system", "content": load_prompt("interview_chat_notes.txt")},
                {"role": "user", "content": "\n\n".join(sections)},
            ],
            tier="basic",
            log_label="interview_chat_notes",
        )

    def research_company(self, company_name: str, scraped_text: str) -> dict:
        logger.info("research_company — company=%r scraped_chars=%d", company_name, len(scraped_text))
        if not self.api_key:
            logger.error("research_company — API key missing")
            raise ValueError(
                "No API key found. Set the OPENROUTER_API_KEY environment variable."
            )

        user_message = (
            f"Company: {company_name}\n\n"
            f"Scraped content from the company's own website:\n{scraped_text}\n\n"
            "From the scraped content above, extract a shallow research brief. "
            "Return ONLY the JSON object described in the system prompt, no markdown."
        )

        model = self._model_for("fast")
        logger.debug("research_company — POST %s tier=fast model=%s timeout=60", self.BASE_URL, model)
        t0 = time.perf_counter()
        try:
            response = requests.post(
                self.BASE_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": load_prompt("research_company.txt"),
                        },
                        {"role": "user", "content": user_message},
                    ],
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "research_company_output",
                            "strict": True,
                            "schema": load_schema("research_company.schema.json"),
                        },
                    },
                },
                timeout=60,
            )
            elapsed = time.perf_counter() - t0
            logger.info("research_company — HTTP %s in %.2fs", response.status_code, elapsed)
            logger.debug("research_company — raw response: %s", response.text[:300])
            response.raise_for_status()
        except Exception:
            logger.exception("research_company — request failed")
            raise

        raw = response.json()["choices"][0]["message"]["content"].strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("research_company — JSON parse failed, raw=%r", raw[:500])
            raise ValueError("AI returned unexpected format — please try again.")

        def _str_list(v) -> list[str]:
            if not isinstance(v, list):
                return []
            return [str(x).strip() for x in v if str(x).strip()]

        result = {
            "core_values": _str_list(data.get("core_values")),
            "recent_projects": _str_list(data.get("recent_projects")),
            "summary": str(data.get("summary", "")).strip(),
        }
        logger.info("research_company — success, values=%d projects=%d", len(result["core_values"]), len(result["recent_projects"]))
        return result


def get_provider() -> OpenRouterProvider:
    return OpenRouterProvider()
