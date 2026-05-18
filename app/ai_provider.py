import json
import logging
import os
import pathlib
import time
from abc import ABC, abstractmethod
from typing import Iterator

import requests

logger = logging.getLogger(__name__)

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


def _load_prompt(name: str) -> str:
    return (_APP_PROMPTS_DIR / name).read_text(encoding="utf-8").strip()


def load_prompt(name: str) -> str:
    return _load_prompt(name)


def default_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8").strip()


def save_prompt(name: str, content: str) -> None:
    _APP_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    (_APP_PROMPTS_DIR / name).write_text(content, encoding="utf-8")

DEFAULT_FAST_MODEL = "google/gemini-2.0-flash-exp:free"

_model_config_cache: dict[str, str] | None = None


def _load_model_config() -> dict[str, str]:
    global _model_config_cache
    if _model_config_cache is not None:
        return _model_config_cache

    defaults = {"fast": DEFAULT_FAST_MODEL}

    _APP_DIR.mkdir(parents=True, exist_ok=True)
    _seed_prompts()
    if not _MODELS_FILE.exists():
        with open(_MODELS_FILE, "w", encoding="utf-8") as f:
            f.write(f"fast={DEFAULT_FAST_MODEL}\n")
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


class AIProvider(ABC):
    @abstractmethod
    def analyze_bullet(self, bullet: str, context: dict) -> str:
        """Returns plain-text feedback + rewrite suggestions for a resume bullet."""
        ...

    @abstractmethod
    def analyze_bullet_stream(self, bullet: str, context: dict) -> Iterator[str]:
        """Yields incremental text chunks for a resume bullet analysis."""
        ...

    @abstractmethod
    def tailor_bullets(self, bullets: list[str], job_description: str) -> list[str]:
        """Returns a list of tailored bullets, same length/order as input."""
        ...

    @abstractmethod
    def generate_resume(
        self, profile: dict, job_description: str, feedback: str | None = None
    ) -> str:
        """Returns a complete, compilable LaTeX resume tailored to the JD."""
        ...

    @abstractmethod
    def grade_resume(self, latex: str, job_description: str) -> dict:
        """Returns {"score": float (0-10), "feedback": str (actionable)}."""
        ...

    @abstractmethod
    def research_company(self, company_name: str, scraped_text: str) -> dict:
        """Returns {"core_values": [str], "recent_projects": [str], "summary": str}."""
        ...


class OpenRouterProvider(AIProvider):
    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        if model:
            self.model = model
        else:
            config = _load_model_config()
            self.model = config["fast"]

        key_hint = f"...{self.api_key[-6:]}" if len(self.api_key) >= 6 else ("(set)" if self.api_key else "(MISSING)")
        logger.debug("OpenRouterProvider init — model=%s api_key=%s", self.model, key_hint)

    def analyze_bullet(self, bullet: str, context: dict) -> str:
        logger.info("analyze_bullet — bullet=%r context=%s", bullet[:120], context)
        if not self.api_key:
            logger.error("analyze_bullet — API key missing")
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

        logger.debug("analyze_bullet — POST %s model=%s timeout=30", self.BASE_URL, self.model)
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
                            "content": _load_prompt("analyze_bullet.txt"),
                        },
                        {"role": "user", "content": user_message},
                    ],
                },
                timeout=30,
            )
            elapsed = time.perf_counter() - t0
            logger.info("analyze_bullet — HTTP %s in %.2fs", response.status_code, elapsed)
            logger.debug("analyze_bullet — raw response: %s", response.text[:300])
            response.raise_for_status()
            result = response.json()["choices"][0]["message"]["content"]
            logger.info("analyze_bullet — success, response length=%d chars", len(result))
            return result
        except Exception:
            logger.exception("analyze_bullet — request failed")
            raise

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
                            "content": _load_prompt("analyze_bullet.txt"),
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
    ) -> Iterator[str]:
        """SSE-stream chat completions, yielding incremental content chunks.

        Mirrors the parsing in `analyze_bullet_stream`. Raises on transport
        failure or non-2xx; a stalled stream trips the per-read timeout.
        """
        if not self.api_key:
            logger.error("%s — API key missing", log_label)
            raise ValueError(
                "No API key found. Set the OPENROUTER_API_KEY environment variable."
            )
        logger.debug("%s — POST %s model=%s stream=True timeout=%s",
                     log_label, self.BASE_URL, self.model, timeout)
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
                    "messages": messages,
                },
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
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        chunk_count += 1
                        yield content
            elapsed = time.perf_counter() - t0
            logger.info("%s — stream done in %.2fs, %d chunks",
                        log_label, elapsed, chunk_count)
        except Exception:
            logger.exception("%s — stream failed", log_label)
            raise

    def tailor_bullets_stream(
        self, bullets: list[str], job_description: str, feedback: str | None = None
    ) -> Iterator[str]:
        logger.info("tailor_bullets_stream — jd=%r bullets=%d feedback=%s",
                    job_description[:120], len(bullets),
                    f"{len(feedback)} chars" if feedback else "none")
        if not bullets:
            return
        numbered = "\n".join(f"{i + 1}. {b}" for i, b in enumerate(bullets))
        user_message = (
            f"Job Description:\n{job_description}\n\n"
            f"Resume Bullets:\n{numbered}\n\n"
            f"Rewrite each bullet to highlight the skills and impact most relevant to "
            f"this job. Return ONLY a JSON array of {len(bullets)} strings, in the same "
            "order as the input. No markdown, no numbering, no explanation."
        )
        if feedback:
            user_message += (
                "\n\nA prior draft of the resume was graded and received the following "
                "feedback. Use it to write stronger bullets in this pass while still "
                "respecting the factual-integrity and structure-preservation constraints.\n"
                f"<feedback>\n{feedback}\n</feedback>"
            )
        yield from self._stream_chat_completion(
            messages=[
                {"role": "system", "content": _load_prompt("tailor_resume.txt")},
                {"role": "user", "content": user_message},
            ],
            log_label="tailor_bullets",
        )

    def tailor_bullets(
        self, bullets: list[str], job_description: str, feedback: str | None = None
    ) -> list[str]:
        if not bullets:
            return []
        raw = "".join(self.tailor_bullets_stream(bullets, job_description, feedback)).strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("tailor_bullets — JSON parse failed, raw=%r", raw[:500])
            raise ValueError("AI returned unexpected format — please try again.")

        if not isinstance(items, list) or not all(isinstance(s, str) for s in items):
            logger.error("tailor_bullets — expected list[str], got %r", type(items).__name__)
            raise ValueError("AI returned unexpected format — please try again.")

        if len(items) != len(bullets):
            logger.error(
                "tailor_bullets — length mismatch: sent %d, got %d", len(bullets), len(items)
            )
            raise ValueError("AI returned unexpected format — please try again.")

        logger.info("tailor_bullets — success, %d bullets returned", len(items))
        return items


    def grade_resume_stream(self, latex: str, job_description: str) -> Iterator[str]:
        logger.info("grade_resume_stream — jd=%r latex_chars=%d",
                    job_description[:120], len(latex))
        user_message = (
            f"Job Description:\n{job_description}\n\n"
            f"Resume LaTeX:\n{latex}\n\n"
            "Grade this resume 0-10 on overall quality and fit to the job. "
            "Return ONLY a JSON object with two keys: "
            '"score" (number 0-10, may use decimals) and '
            '"feedback" (string with specific, actionable improvements: '
            "what to add, remove, or rephrase). No markdown, no commentary."
        )
        yield from self._stream_chat_completion(
            messages=[
                {"role": "system", "content": _load_prompt("grade_resume.txt")},
                {"role": "user", "content": user_message},
            ],
            log_label="grade_resume",
        )

    def grade_resume(self, latex: str, job_description: str) -> dict:
        raw = "".join(self.grade_resume_stream(latex, job_description)).strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("grade_resume — JSON parse failed, raw=%r", raw[:500])
            raise ValueError("AI returned unexpected format — please try again.")

        if not isinstance(obj, dict) or "score" not in obj or "feedback" not in obj:
            logger.error("grade_resume — missing keys, got %r", obj)
            raise ValueError("AI returned unexpected format — please try again.")

        try:
            score = float(obj["score"])
        except (TypeError, ValueError):
            logger.error("grade_resume — score not numeric: %r", obj.get("score"))
            raise ValueError("AI returned unexpected format — please try again.")

        feedback = str(obj["feedback"])
        logger.info("grade_resume — score=%.2f feedback_chars=%d", score, len(feedback))
        return {"score": score, "feedback": feedback}


    def _build_generate_resume_messages(
        self, profile: dict, job_description: str, feedback: str | None
    ) -> list[dict]:
        import json as _json

        profile_json = _json.dumps({
            "experience": profile.get("experience", []),
            "projects": profile.get("projects", []),
            "education": profile.get("education", []),
            "skills": profile.get("skills", []),
        }, indent=2)

        template = get_resume_template().strip()
        if template:
            user_message = (
                f"Job Description:\n{job_description}\n\n"
                f"Candidate Profile (JSON):\n{profile_json}\n\n"
                "Write a complete, compilable LaTeX resume from this profile. "
                "The bullets in the profile JSON are already tailored to this job by "
                "an upstream step — reproduce them VERBATIM. Do not rewrite, shorten, "
                "merge, split, or rephrase bullet text. Your job is LaTeX layout, "
                "section ordering, and the skills section (where you may weave in "
                "JD keywords). Cover all populated sections (Experience, Projects, "
                "Education, Skills). "
                "Escape LaTeX special characters in user-provided text. "
                "Return ONLY raw LaTeX source starting with \\documentclass — "
                "no markdown fences, no commentary, no explanation.\n\n"
                "Use the following LaTeX template as the structural base for the "
                "resume. Preserve its documentclass, packages, geometry, command "
                "definitions, and overall layout; only adapt the content sections "
                "to fit the candidate profile.\n\n"
                "<template>\n"
                f"{template}\n"
                "</template>"
            )
        else:
            user_message = (
                f"Job Description:\n{job_description}\n\n"
                f"Candidate Profile (JSON):\n{profile_json}\n\n"
                "Write a complete, compilable LaTeX resume from this profile. "
                "The bullets in the profile JSON are already tailored to this job by "
                "an upstream step — reproduce them VERBATIM. Do not rewrite, shorten, "
                "merge, split, or rephrase bullet text. Your job is LaTeX layout, "
                "section ordering, and the skills section (where you may weave in "
                "JD keywords). Cover all populated sections (Experience, Projects, "
                "Education, Skills). Use article class with "
                "only these packages: geometry, hyperref, enumitem, titlesec. "
                "Keep margins tight (~0.75in), single column, clean and readable. "
                "Escape LaTeX special characters in user-provided text. "
                "Return ONLY raw LaTeX source starting with \\documentclass — "
                "no markdown fences, no commentary, no explanation."
            )

        if feedback:
            user_message += (
                "\n\nA prior draft did not compile or did not fit the page cap. "
                "Apply the following feedback for LaTeX structure, layout, and "
                "page-fit only. Do NOT modify bullet text — bullet wording is owned "
                "by an upstream step and must be reproduced verbatim.\n"
                f"<feedback>\n{feedback}\n</feedback>"
            )

        return [
            {"role": "system", "content": _load_prompt("generate_resume.txt")},
            {"role": "user", "content": user_message},
        ]

    def generate_resume_stream(
        self, profile: dict, job_description: str, feedback: str | None = None
    ) -> Iterator[str]:
        logger.info(
            "generate_resume_stream — jd=%r feedback=%s",
            job_description[:120],
            f"{len(feedback)} chars" if feedback else "none",
        )
        messages = self._build_generate_resume_messages(profile, job_description, feedback)
        yield from self._stream_chat_completion(
            messages=messages,
            log_label="generate_resume",
        )

    def generate_resume(
        self, profile: dict, job_description: str, feedback: str | None = None
    ) -> str:
        raw = "".join(self.generate_resume_stream(profile, job_description, feedback)).strip()

        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("latex"):
                raw = raw[5:]
            elif raw.startswith("tex"):
                raw = raw[3:]
            raw = raw.strip()
            if raw.endswith("```"):
                raw = raw[:-3].strip()

        logger.info("generate_resume — success, LaTeX length=%d chars", len(raw))
        return raw


    def research_company(self, company_name: str, scraped_text: str) -> dict:
        logger.info("research_company — company=%r scraped_chars=%d", company_name, len(scraped_text))
        if not self.api_key:
            logger.error("research_company — API key missing")
            raise ValueError(
                "No API key found. Set the OPENROUTER_API_KEY environment variable."
            )

        import json as _json

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
                            "content": _load_prompt("research_company.txt"),
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
            data = _json.loads(raw)
        except _json.JSONDecodeError:
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


def save_model_config(fast: str) -> None:
    global _model_config_cache
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    with open(_MODELS_FILE, "w", encoding="utf-8") as f:
        f.write(f"fast={fast.strip()}\n")
    _model_config_cache = {"fast": fast.strip()}


def get_provider() -> AIProvider:
    return OpenRouterProvider()
