import datetime
import json
import logging
import os
import pathlib
import time
from typing import Iterator

import requests

logger = logging.getLogger(__name__)

# Out-of-band marker prefix for streamed tool-event lines. Downstream
# collectors (e.g. ResumeGenerator._collect_stream) detect this prefix to
# route tool events to the UI without polluting the model's text output.
TOOL_EVENT_PREFIX = "\x1e"

_APP_DIR = pathlib.Path.home() / "Library" / "Application Support" / "InternApplier"
_MODELS_FILE = _APP_DIR / "models.txt"
_SETTINGS_FILE = _APP_DIR / "settings.json"
_PROMPTS_DIR = pathlib.Path(__file__).parent.parent / "prompts"
_APP_PROMPTS_DIR = _APP_DIR / "prompts"


def _seed_prompts() -> None:
    _APP_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    for src in _PROMPTS_DIR.glob("*.txt"):
        dst = _APP_PROMPTS_DIR / src.name
        if not dst.exists():
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def resync_all_prompts() -> None:
    _APP_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    for src in _PROMPTS_DIR.glob("*.txt"):
        dst = _APP_PROMPTS_DIR / src.name
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def load_prompt(name: str) -> str:
    return (_APP_PROMPTS_DIR / name).read_text(encoding="utf-8").strip()


def default_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8").strip()


def save_prompt(name: str, content: str) -> None:
    _APP_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    (_APP_PROMPTS_DIR / name).write_text(content, encoding="utf-8")

DEFAULT_FAST_MODEL = "google/gemini-2.0-flash-exp:free"
DEFAULT_POWERFUL_MODEL = "openai/gpt-4o-mini"

_model_config_cache: dict[str, str] | None = None


def _load_model_config() -> dict[str, str]:
    global _model_config_cache
    if _model_config_cache is not None:
        return _model_config_cache

    defaults = {"fast": DEFAULT_FAST_MODEL, "powerful": DEFAULT_POWERFUL_MODEL}

    _APP_DIR.mkdir(parents=True, exist_ok=True)
    _seed_prompts()
    if not _MODELS_FILE.exists():
        with open(_MODELS_FILE, "w", encoding="utf-8") as f:
            f.write(f"fast={DEFAULT_FAST_MODEL}\n")
            f.write(f"powerful={DEFAULT_POWERFUL_MODEL}\n")
        _model_config_cache = defaults
        return _model_config_cache

    config = dict(defaults)
    with open(_MODELS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip().lower()
            value = value.strip()
            if key in defaults and value:
                config[key] = value

    _model_config_cache = config
    return _model_config_cache


class OpenRouterProvider:
    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        tier: str = "fast",
    ):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        if model:
            self.model = model
        else:
            config = _load_model_config()
            self.model = config.get(tier) or config["fast"]

        key_hint = f"...{self.api_key[-6:]}" if len(self.api_key) >= 6 else ("(set)" if self.api_key else "(MISSING)")
        logger.debug("OpenRouterProvider init — tier=%s model=%s api_key=%s", tier, self.model, key_hint)

    def analyze_bullet_stream(self, bullet: str, context: dict) -> Iterator[str]:
        logger.info("analyze_bullet_stream — bullet=%r context=%s", bullet[:120], context)
        if not self.api_key:
            logger.error("analyze_bullet_stream — API key missing")
            raise ValueError(
                "No API key found. Set the OPENROUTER_API_KEY environment variable."
            )

        context_line = _format_context(context)
        user_message = (
            f"{context_line}\n\n"
            f'Resume bullet: "{bullet}"\n\n'
            "Please provide:\n"
            "1. CRITIQUE: A 1-2 sentence assessment of this bullet's weaknesses "
            "(e.g., missing metrics, weak action verb, unclear impact).\n"
            "2. REWRITE A: An improved version of this bullet.\n"
            "3. REWRITE B: A second, alternative improved version."
        )

        logger.debug("analyze_bullet_stream — POST %s model=%s stream=True", self.BASE_URL, self.model)
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
                json={
                    "model": self.model,
                    "stream": True,
                    "messages": [
                        {
                            "role": "system",
                            "content": load_prompt("analyze_bullet.txt"),
                        },
                        {"role": "user", "content": user_message},
                    ],
                },
                stream=True,
                timeout=60,
            ) as response:
                response.raise_for_status()
                response.encoding = "utf-8"
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    if line.startswith(": "):
                        continue
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        data = json.loads(payload)
                    except json.JSONDecodeError:
                        logger.debug("analyze_bullet_stream — skipping non-JSON line: %r", payload[:120])
                        continue
                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        chunk_count += 1
                        yield content
            elapsed = time.perf_counter() - t0
            logger.info("analyze_bullet_stream — done in %.2fs, %d chunks", elapsed, chunk_count)
        except Exception:
            logger.exception("analyze_bullet_stream — request failed")
            raise

    def _stream_chat_completion(
        self,
        messages: list[dict],
        *,
        log_label: str,
        timeout: tuple[float, float] = (10.0, 30.0),
        tools: list[dict] | None = None,
        max_tool_rounds: int = 4,
        tool_overrides: dict | None = None,
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

        from .generate_resume.agent_tools import TOOL_HANDLERS

        logger.debug("%s — POST %s model=%s stream=True timeout=%s tools=%s",
                     log_label, self.BASE_URL, self.model, timeout,
                     [t["function"]["name"] for t in tools] if tools else None)

        messages = list(messages)
        rounds_used = 0

        while True:
            payload_json: dict = {
                "model": self.model,
                "stream": True,
                "messages": messages,
            }
            if tools:
                payload_json["tools"] = tools
                payload_json["tool_choice"] = (
                    "none" if rounds_used >= max_tool_rounds else "auto"
                )

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
                        if not line:
                            continue
                        if line.startswith(": "):
                            continue
                        if not line.startswith("data: "):
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
                if round_content:
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

    def fix_latex_stream(self, latex: str, compile_error: str) -> Iterator[str]:
        from .generate_resume.agent_tools import (
            OPENAI_TOOL_SCHEMAS,
            extract_preamble,
            make_test_compile,
        )

        logger.info("fix_latex_stream — latex_chars=%d error_chars=%d",
                    len(latex), len(compile_error))
        preamble = extract_preamble(latex)
        logger.debug(
            "fix_latex_stream — preamble extracted: %s",
            f"{len(preamble)} chars" if preamble else "none (minimal fallback)",
        )
        user_message = (
            f"Broken LaTeX source:\n{latex}\n\n"
            f"pdflatex error log:\n{compile_error}\n\n"
            "Repair the syntax and return the corrected, complete LaTeX "
            "document as your final assistant message — no prose, no fences."
        )
        yield from self._stream_chat_completion(
            messages=[
                {"role": "system", "content": load_prompt("fix_latex.txt")},
                {"role": "user", "content": user_message},
            ],
            log_label="fix_latex",
            tools=[OPENAI_TOOL_SCHEMAS["test_compile"]],
            tool_overrides={"test_compile": make_test_compile(preamble)},
        )

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
        if profile:
            profile_json = json.dumps({
                "experience": profile.get("experience", []),
                "projects": profile.get("projects", []),
                "education": profile.get("education", []),
                "awards": profile.get("awards", []),
                "skills": profile.get("skills", []),
                "hobbies": profile.get("hobbies", []),
            }, indent=2)
            profile_block = f"<profile>\n{profile_json}\n</profile>\n\n"
        else:
            profile_block = ""
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
        from .generate_resume.agent_tools import OPENAI_TOOL_SCHEMAS

        yield from self._stream_chat_completion(
            messages=[
                {"role": "system", "content": load_prompt("grade_resume.txt")},
                {"role": "user", "content": user_message},
            ],
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
        profile_json = json.dumps({
            "experience": profile.get("experience", []),
            "projects": profile.get("projects", []),
            "education": profile.get("education", []),
            "awards": profile.get("awards", []),
            "skills": profile.get("skills", []),
            "hobbies": profile.get("hobbies", []),
        }, indent=2)

        sections: list[str] = [
            f"<today>{today}</today>",
            f"<job_description>\n{job_description}\n</job_description>",
            f"<profile>\n{profile_json}\n</profile>",
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
        from .generate_resume.agent_tools import OPENAI_TOOL_SCHEMAS

        messages = self._build_generate_resume_messages(
            profile, job_description, feedback, previous_latex, today,
            company_research=company_research,
        )
        yield from self._stream_chat_completion(
            messages=messages,
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
        profile_json = json.dumps({
            "experience": profile.get("experience", []),
            "projects": profile.get("projects", []),
            "education": profile.get("education", []),
            "awards": profile.get("awards", []),
            "skills": profile.get("skills", []),
            "hobbies": profile.get("hobbies", []),
        }, indent=2)

        sections: list[str] = [
            f"<today>{today}</today>",
            f"<question>\n{question}\n</question>",
        ]
        if company_name:
            sections.append(f"<company_name>{company_name}</company_name>")
        sections.append(f"<profile>\n{profile_json}\n</profile>")
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
        profile_json = json.dumps({
            "experience": profile.get("experience", []),
            "projects": profile.get("projects", []),
            "education": profile.get("education", []),
            "awards": profile.get("awards", []),
            "skills": profile.get("skills", []),
            "hobbies": profile.get("hobbies", []),
        }, indent=2)

        sections: list[str] = [
            f"<today>{today}</today>",
            f"<question>\n{question}\n</question>",
            f"<response>\n{response}\n</response>",
        ]
        if company_name:
            sections.append(f"<company_name>{company_name}</company_name>")
        sections.append(f"<profile>\n{profile_json}\n</profile>")
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
            log_label="grade_interview_response",
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
            "Return a JSON object with exactly these keys:\n"
            '  "core_values": array of 3-6 capturing the company\'s '
            "stated values, mission, or culture pillars.\n"
            '  "recent_projects": array of 3-6 short strings describing recent '
            "products, launches, initiatives, or news mentioned on the site. Give a small description of each.\n"
            '  "summary": a 2-3 sentence plain-text summary of what the company does '
            "and its current focus.\n"
            "If a field cannot be inferred from the content, return an empty array "
            "or empty string for it. Return ONLY the JSON object, no markdown."
        )

        logger.debug("research_company — POST %s model=%s timeout=60", self.BASE_URL, self.model)
        t0 = time.perf_counter()
        try:
            response = requests.post(
                self.BASE_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": load_prompt("research_company.txt"),
                        },
                        {"role": "user", "content": user_message},
                    ],
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


def _format_tool_event(
    name: str, round_idx: int, args: dict, result: dict
) -> str:
    """Render a tool-call event as a multi-line block for UI display."""
    latex_arg = args.get("latex") if isinstance(args, dict) else None
    latex_chars = len(latex_arg) if isinstance(latex_arg, str) else 0
    ok = result.get("ok")
    badge = "✓" if ok else "✗"

    parts = [f"[tool {badge}] {name} (round {round_idx}, latex={latex_chars} chars)"]
    if name == "page_length" and ok:
        fill = result.get("fill")
        cap = result.get("page_cap")
        try:
            parts.append(f"  → fill={float(fill):.3f} / page_cap={cap}")
        except (TypeError, ValueError):
            parts.append(f"  → fill={fill} / page_cap={cap}")
    elif ok:
        parts.append("  → ok")
    else:
        excerpt = (result.get("log_excerpt") or result.get("error") or "").strip()
        if excerpt:
            # Indent excerpt for readability; cap to a few lines.
            lines = excerpt.splitlines()[:6]
            parts.append("  → failed:")
            parts.extend(f"      {ln}" for ln in lines)
        else:
            parts.append("  → failed")
    return "\n".join(parts) + "\n"


def _format_context(context: dict) -> str:
    kind = context.get("type", "")
    if kind == "experience":
        return (
            f"Context: Work experience at {context.get('company', 'a company')}, "
            f"role: {context.get('role', 'unknown role')}."
        )
    if kind == "project":
        return f"Context: Personal/academic project — {context.get('name', 'unnamed project')}."
    if kind == "education":
        return (
            f"Context: Education at {context.get('school', 'a school')}, "
            f"degree: {context.get('degree', 'unknown degree')}."
        )
    return ""


_settings_cache: dict | None = None


def _load_settings() -> dict:
    global _settings_cache
    if _settings_cache is not None:
        return _settings_cache
    if not _SETTINGS_FILE.exists():
        _settings_cache = {}
        return _settings_cache
    try:
        with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        _settings_cache = data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        _settings_cache = {}
    return _settings_cache


def get_resume_template() -> str:
    return str(_load_settings().get("resume_template", ""))


def save_resume_template(text: str) -> None:
    global _settings_cache
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    current = dict(_load_settings())
    current["resume_template"] = text
    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    _settings_cache = current


DEFAULT_RESUME_PAGE_CAP = 1


def get_resume_page_cap() -> int:
    val = _load_settings().get("resume_page_cap", DEFAULT_RESUME_PAGE_CAP)
    try:
        n = int(val)
    except (TypeError, ValueError):
        return DEFAULT_RESUME_PAGE_CAP
    return n if n >= 1 else DEFAULT_RESUME_PAGE_CAP


def save_resume_page_cap(pages: int) -> None:
    global _settings_cache
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    current = dict(_load_settings())
    current["resume_page_cap"] = int(pages)
    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    _settings_cache = current


DEFAULT_RESUME_OUTPUT_DIR = pathlib.Path.home() / "Documents" / "Resumes"


def get_resume_output_dir() -> pathlib.Path:
    val = _load_settings().get("resume_output_dir")
    if not val:
        return DEFAULT_RESUME_OUTPUT_DIR
    return pathlib.Path(str(val)).expanduser()


def save_resume_output_dir(path: str) -> None:
    global _settings_cache
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    current = dict(_load_settings())
    current["resume_output_dir"] = str(path).strip()
    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    _settings_cache = current


DEFAULT_MAX_GENERATION_ATTEMPTS = 2


def get_max_generation_attempts() -> int:
    val = _load_settings().get("max_generation_attempts", DEFAULT_MAX_GENERATION_ATTEMPTS)
    try:
        n = int(val)
    except (TypeError, ValueError):
        return DEFAULT_MAX_GENERATION_ATTEMPTS
    return n if n >= 1 else DEFAULT_MAX_GENERATION_ATTEMPTS


def save_max_generation_attempts(n: int) -> None:
    global _settings_cache
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    current = dict(_load_settings())
    current["max_generation_attempts"] = int(n)
    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    _settings_cache = current


DEFAULT_MAX_LATEX_FIX_ATTEMPTS = 2


def get_max_latex_fix_attempts() -> int:
    val = _load_settings().get("max_latex_fix_attempts", DEFAULT_MAX_LATEX_FIX_ATTEMPTS)
    try:
        n = int(val)
    except (TypeError, ValueError):
        return DEFAULT_MAX_LATEX_FIX_ATTEMPTS
    return n if n >= 0 else DEFAULT_MAX_LATEX_FIX_ATTEMPTS


def save_max_latex_fix_attempts(n: int) -> None:
    global _settings_cache
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    current = dict(_load_settings())
    current["max_latex_fix_attempts"] = int(n)
    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    _settings_cache = current


DEFAULT_AUTO_RESYNC_PROMPTS = False


def get_auto_resync_prompts() -> bool:
    return bool(_load_settings().get("auto_resync_prompts", DEFAULT_AUTO_RESYNC_PROMPTS))


def save_auto_resync_prompts(enabled: bool) -> None:
    global _settings_cache
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    current = dict(_load_settings())
    current["auto_resync_prompts"] = bool(enabled)
    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    _settings_cache = current


def save_model_config(fast: str, powerful: str) -> None:
    global _model_config_cache
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    fast = fast.strip()
    powerful = powerful.strip()
    with open(_MODELS_FILE, "w", encoding="utf-8") as f:
        f.write(f"fast={fast}\n")
        f.write(f"powerful={powerful}\n")
    _model_config_cache = {"fast": fast, "powerful": powerful}


def get_provider(tier: str = "fast") -> OpenRouterProvider:
    return OpenRouterProvider(tier=tier)
