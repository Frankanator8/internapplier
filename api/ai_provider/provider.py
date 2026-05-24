"""Domain-specific completion methods on top of :mod:`http_client`.

Each public method builds messages from prompt templates + context, hands
them to the client's :meth:`stream_chat_completion` or :meth:`post_json`,
and yields/returns the result. Transport, tool-call dispatching, and
token-usage accounting all live in :mod:`http_client`.
"""
from __future__ import annotations

import json
import logging
from typing import Iterator

from .formatting import (
    _common_context_sections,
    _format_context,
    _profile_json,
    _today,
    strip_code_fence,
)
from .http_client import OpenRouterHTTPClient
from .prompts import load_prompt, load_schema
from .settings import _load_model_config, get_resume_template  # noqa: F401  (re-export for tests)
from ..app_settings import get_writing_sample

logger = logging.getLogger(__name__)


class OpenRouterProvider:
    """Facade exposing domain-specific completions to the rest of the app.

    All network plumbing lives in :class:`OpenRouterHTTPClient`. Methods
    here are responsible only for prompt construction.
    """

    def __init__(self, api_key: str | None = None):
        self._client = OpenRouterHTTPClient(api_key=api_key)

    @property
    def api_key(self) -> str:
        return self._client.api_key

    def _stream_chat_completion(self, *args, **kwargs):
        return self._client.stream_chat_completion(*args, **kwargs)

    # ── Streaming completions ───────────────────────────────────────────────

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
        yield from self._client.stream_chat_completion(
            messages=[
                {"role": "system", "content": load_prompt("analyze_bullet.txt")},
                {"role": "user", "content": user_message},
            ],
            tier="basic",
            log_label="analyze_bullet_stream",
            timeout=(10.0, 60.0),
        )

    def grade_resume_stream(
        self,
        resume_json: dict,
        job_description: str,
        *,
        fill: float | None = None,
        page_cap: float | None = None,
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
        resume_text = (
            json.dumps(resume_json, separators=(",", ":"))
            if resume_json is not None else ""
        )
        logger.info(
            "grade_resume_stream — jd=%r resume_chars=%d fill=%s page_cap=%s research=%s profile=%s",
            job_description[:120], len(resume_text),
            f"{fill:.3f}" if fill is not None else None,
            f"{page_cap:.3f}" if page_cap is not None else None,
            f"{len(company_research)} keys" if company_research else "none",
            profile_summary,
        )
        page_status = (
            f"<page_status>fill={fill:.2f} page_cap={page_cap:.2f}</page_status>\n\n"
            if fill is not None and page_cap is not None else ""
        )
        research_block = (
            f"<company_research>\n{json.dumps(company_research, separators=(',', ':'))}\n</company_research>\n\n"
            if company_research else ""
        )
        profile_block = (
            f"<profile>\n{_profile_json(profile)}\n</profile>\n\n" if profile else ""
        )
        static_text = (
            f"<today>{_today(today)}</today>\n\n"
            f"{profile_block}"
            f"{research_block}"
            f"Job Description:\n{job_description}"
        )
        dynamic_text = (
            f"{page_status}"
            f"Resume JSON:\n{resume_text}\n\n"
            "Grade this resume against the job description following the system "
            "instructions exactly."
        )
        yield from self._client.stream_chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": [{
                        "type": "text",
                        "text": load_prompt("grade_resume.txt"),
                        "cache_control": {"type": "ephemeral"},
                    }],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": static_text,
                            "cache_control": {"type": "ephemeral"},
                        },
                        {"type": "text", "text": dynamic_text},
                    ],
                },
            ],
            tier="fast",
            log_label="grade_resume",
        )

    def generate_resume_stream(
        self,
        profile: dict,
        job_description: str,
        feedback: str | None = None,
        previous_resume: dict | None = None,
        today: str | None = None,
        company_research: dict | None = None,
    ) -> Iterator[str]:
        logger.info(
            "generate_resume_stream — jd=%r feedback=%s previous_resume=%s research=%s",
            job_description[:120],
            f"{len(feedback)} chars" if feedback else "none",
            "yes" if previous_resume else "none",
            f"{len(company_research)} keys" if company_research else "none",
        )
        from ..generate_resume.agent_tools import OPENAI_TOOL_SCHEMAS

        messages = self._build_generate_resume_messages(
            profile, job_description, feedback, previous_resume, today,
            company_research=company_research,
        )
        yield from self._client.stream_chat_completion(
            messages=messages,
            tier="powerful",
            log_label="generate_resume",
            tools=[OPENAI_TOOL_SCHEMAS["page_length"]],
        )

    def _build_generate_resume_messages(
        self,
        profile: dict,
        job_description: str,
        feedback: str | None,
        previous_resume: dict | None = None,
        today: str | None = None,
        company_research: dict | None = None,
    ) -> list[dict]:
        from .keyword_extractor import extract_jd_keywords, format_jd_signals

        signals = extract_jd_keywords(job_description)
        static_sections: list[str] = [
            f"<today>{_today(today)}</today>",
            f"<jd_signals>\n{format_jd_signals(signals)}\n</jd_signals>",
        ]
        if company_research:
            static_sections.append(
                f"<company_research>\n{json.dumps(company_research, separators=(',', ':'))}\n</company_research>"
            )
        if get_resume_template().strip():
            static_sections.append(
                "<template_note>\nA Jinja-style LaTeX template is configured server-side. "
                "You do not interact with it; emit JSON only.\n</template_note>"
            )
        static_sections.append(f"<profile>\n{_profile_json(profile)}\n</profile>")

        user_content: list[dict] = [{
            "type": "text",
            "text": "\n\n".join(static_sections),
            "cache_control": {"type": "ephemeral"},
        }]
        if previous_resume:
            user_content.append({
                "type": "text",
                "text": f"<previous_draft>\n{json.dumps(previous_resume, separators=(',', ':'))}\n</previous_draft>",
                "cache_control": {"type": "ephemeral"},
            })
        if feedback:
            user_content.append({
                "type": "text",
                "text": f"<feedback>\n{feedback}\n</feedback>",
            })

        return [
            {
                "role": "system",
                "content": [{
                    "type": "text",
                    "text": load_prompt("generate_resume.txt"),
                    "cache_control": {"type": "ephemeral"},
                }],
            },
            {"role": "user", "content": user_content},
        ]

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
            question[:120], company_name,
            f"{len(company_research)} keys" if company_research else "none",
            f"{len(job_description)} chars" if job_description else "none",
        )
        sections = [
            f"<today>{_today(today)}</today>",
            f"<question>\n{question}\n</question>",
        ]
        sections.extend(_common_context_sections(
            profile=profile, company_name=company_name,
            company_research=company_research, job_description=job_description,
        ))
        writing_sample = (get_writing_sample() or "").strip()
        if writing_sample:
            sections.append(f"<writing_sample>\n{writing_sample}\n</writing_sample>")

        yield from self._client.stream_chat_completion(
            messages=[
                {"role": "system", "content": load_prompt("answer_question.txt")},
                {"role": "user", "content": "\n\n".join(sections)},
            ],
            tier="basic",
            log_label="answer_question",
            sampling={
                "temperature": 0.9,
                "frequency_penalty": 0.4,
                "presence_penalty": 0.2,
            },
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
            question[:120], len(response), company_name,
            f"{len(company_research)} keys" if company_research else "none",
            f"{len(job_description)} chars" if job_description else "none",
        )
        sections = [
            f"<today>{_today(today)}</today>",
            f"<question>\n{question}\n</question>",
            f"<response>\n{response}\n</response>",
        ]
        sections.extend(_common_context_sections(
            profile=profile, company_name=company_name,
            company_research=company_research, job_description=job_description,
        ))

        yield from self._client.stream_chat_completion(
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
            len(history), company_name,
            f"{len(company_research)} keys" if company_research else "none",
            f"{len(job_description)} chars" if job_description else "none",
        )
        sections = [f"<today>{_today(today)}</today>"]
        sections.extend(_common_context_sections(
            profile=profile, company_name=company_name,
            company_research=company_research, job_description=job_description,
        ))

        messages: list[dict] = [
            {"role": "system", "content": load_prompt("interview_chat.txt")},
            {"role": "user", "content": "\n\n".join(sections)},
        ]
        for turn in history:
            role = turn.get("role")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        yield from self._client.stream_chat_completion(
            messages=messages, tier="basic", log_label="chat_interview",
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
        transcript_text = "\n\n".join(
            f"{turn['role']}: {(turn.get('content') or '').strip()}"
            for turn in history
            if turn.get("role") in ("user", "assistant")
            and (turn.get("content") or "").strip()
        )
        sections = [
            f"<today>{_today(today)}</today>",
            f"<prior_notes>\n{prior_notes or ''}\n</prior_notes>",
            f"<transcript>\n{transcript_text}\n</transcript>",
        ]
        sections.extend(_common_context_sections(
            profile=profile, company_name=company_name,
            company_research=company_research, job_description=job_description,
        ))

        yield from self._client.stream_chat_completion(
            messages=[
                {"role": "system", "content": load_prompt("interview_chat_notes.txt")},
                {"role": "user", "content": "\n\n".join(sections)},
            ],
            tier="basic",
            log_label="interview_chat_notes",
        )

    # ── Non-streaming ───────────────────────────────────────────────────────

    def research_company(self, company_name: str, scraped_text: str) -> dict:
        logger.info(
            "research_company — company=%r scraped_chars=%d",
            company_name, len(scraped_text),
        )
        user_message = (
            f"Company: {company_name}\n\n"
            f"Scraped content from the company's own website:\n{scraped_text}\n\n"
            "From the scraped content above, extract a shallow research brief. "
            "Return ONLY the JSON object described in the system prompt, no markdown."
        )
        raw = self._client.post_json(
            messages=[
                {"role": "system", "content": load_prompt("research_company.txt")},
                {"role": "user", "content": user_message},
            ],
            tier="fast",
            log_label="research_company",
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "research_company_output",
                    "strict": True,
                    "schema": load_schema("research_company.schema.json"),
                },
            },
            timeout=60,
        )

        try:
            data = json.loads(strip_code_fence(raw, ("json",)))
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
        logger.info(
            "research_company — success, values=%d projects=%d",
            len(result["core_values"]), len(result["recent_projects"]),
        )
        return result


def get_provider() -> OpenRouterProvider:
    return OpenRouterProvider()
