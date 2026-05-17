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
    def tailor_resume(self, profile: dict, job_description: str) -> list[dict]:
        """Returns list of {section, entry, original, tailored} dicts."""
        ...

    @abstractmethod
    def generate_resume(self, profile: dict, job_description: str) -> str:
        """Returns a complete, compilable LaTeX resume tailored to the JD."""
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

    def tailor_resume(self, bullets: list[str], job_description: str) -> list[str]:
        logger.info("tailor_resume — jd=%r bullets=%d", job_description[:120], len(bullets))
        if not bullets:
            return []
        if not self.api_key:
            logger.error("tailor_resume — API key missing")
            raise ValueError(
                "No API key found. Set the OPENROUTER_API_KEY environment variable."
            )

        numbered = "\n".join(f"{i + 1}. {b}" for i, b in enumerate(bullets))
        user_message = (
            f"Job Description:\n{job_description}\n\n"
            f"Resume Bullets:\n{numbered}\n\n"
            f"Rewrite each bullet to highlight the skills and impact most relevant to "
            f"this job. Return ONLY a JSON array of {len(bullets)} strings, in the same "
            "order as the input. No markdown, no numbering, no explanation."
        )

        logger.debug("tailor_resume — POST %s model=%s timeout=60", self.BASE_URL, self.model)
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
                            "content": _load_prompt("tailor_resume.txt"),
                        },
                        {"role": "user", "content": user_message},
                    ],
                },
                timeout=60,
            )
            elapsed = time.perf_counter() - t0
            logger.info("tailor_resume — HTTP %s in %.2fs", response.status_code, elapsed)
            logger.debug("tailor_resume — raw response: %s", response.text[:300])
            response.raise_for_status()
        except Exception:
            logger.exception("tailor_resume — request failed")
            raise

        raw = response.json()["choices"][0]["message"]["content"].strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("tailor_resume — JSON parse failed, raw=%r", raw[:500])
            raise ValueError("AI returned unexpected format — please try again.")

        if not isinstance(items, list) or not all(isinstance(s, str) for s in items):
            logger.error("tailor_resume — expected list[str], got %r", type(items).__name__)
            raise ValueError("AI returned unexpected format — please try again.")

        if len(items) != len(bullets):
            logger.error(
                "tailor_resume — length mismatch: sent %d, got %d", len(bullets), len(items)
            )
            raise ValueError("AI returned unexpected format — please try again.")

        logger.info("tailor_resume — success, %d bullets returned", len(items))
        return items


    def generate_resume(self, profile: dict, job_description: str) -> str:
        logger.info("generate_resume — jd=%r", job_description[:120])
        if not self.api_key:
            logger.error("generate_resume — API key missing")
            raise ValueError(
                "No API key found. Set the OPENROUTER_API_KEY environment variable."
            )

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
                "Write a complete, compilable LaTeX resume tailored to this job. "
                "Naturally weave the most relevant keywords and skills from the job "
                "description into the bullet points and the skills section so the "
                "resume reads as a strong match. Cover all populated sections "
                "(Experience, Projects, Education, Skills). "
                "Escape LaTeX special characters in user-provided text. "
                "Return ONLY raw LaTeX source starting with \\documentclass — "
                "no markdown fences, no commentary, no explanation.\n\n"
                "Use the following LaTeX template as the structural base for the "
                "resume. Preserve its documentclass, packages, geometry, command "
                "definitions, and overall layout; only adapt the content sections "
                "to fit the candidate profile and job description.\n\n"
                "<template>\n"
                f"{template}\n"
                "</template>"
            )
        else:
            user_message = (
                f"Job Description:\n{job_description}\n\n"
                f"Candidate Profile (JSON):\n{profile_json}\n\n"
                "Write a complete, compilable LaTeX resume tailored to this job. "
                "Naturally weave the most relevant keywords and skills from the job "
                "description into the bullet points and the skills section so the "
                "resume reads as a strong match. Cover all populated sections "
                "(Experience, Projects, Education, Skills). Use article class with "
                "only these packages: geometry, hyperref, enumitem, titlesec. "
                "Keep margins tight (~0.75in), single column, clean and readable. "
                "Escape LaTeX special characters in user-provided text. "
                "Return ONLY raw LaTeX source starting with \\documentclass — "
                "no markdown fences, no commentary, no explanation."
            )

        logger.debug("generate_resume — POST %s model=%s timeout=90", self.BASE_URL, self.model)
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
                            "content": _load_prompt("generate_resume.txt"),
                        },
                        {"role": "user", "content": user_message},
                    ],
                },
                timeout=90,
            )
            elapsed = time.perf_counter() - t0
            logger.info("generate_resume — HTTP %s in %.2fs", response.status_code, elapsed)
            logger.debug("generate_resume — raw response: %s", response.text[:300])
            response.raise_for_status()
        except Exception:
            logger.exception("generate_resume — request failed")
            raise

        raw = response.json()["choices"][0]["message"]["content"].strip()

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


def save_model_config(fast: str) -> None:
    global _model_config_cache
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    with open(_MODELS_FILE, "w", encoding="utf-8") as f:
        f.write(f"fast={fast.strip()}\n")
    _model_config_cache = {"fast": fast.strip()}


def get_provider() -> AIProvider:
    return OpenRouterProvider()
