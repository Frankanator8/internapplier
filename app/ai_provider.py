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
_PROMPTS_DIR = pathlib.Path(__file__).parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8").strip()

DEFAULT_FAST_MODEL = "google/gemini-2.0-flash-exp:free"
DEFAULT_POWERFUL_MODEL = "openai/gpt-4o-mini"

_model_config_cache: dict[str, str] | None = None


def _load_model_config() -> dict[str, str]:
    global _model_config_cache
    if _model_config_cache is not None:
        return _model_config_cache

    defaults = {"fast": DEFAULT_FAST_MODEL, "powerful": DEFAULT_POWERFUL_MODEL}

    _APP_DIR.mkdir(parents=True, exist_ok=True)
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
        tier: str = "powerful",
    ):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        if model:
            self.model = model
        else:
            config = _load_model_config()
            self.model = config.get(tier, config["powerful"])

        key_hint = f"...{self.api_key[-6:]}" if len(self.api_key) >= 6 else ("(set)" if self.api_key else "(MISSING)")
        logger.debug("OpenRouterProvider init — tier=%s model=%s api_key=%s", tier, self.model, key_hint)

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

    def tailor_resume(self, profile: dict, job_description: str) -> list[dict]:
        logger.info("tailor_resume — jd=%r", job_description[:120])
        if not self.api_key:
            logger.error("tailor_resume — API key missing")
            raise ValueError(
                "No API key found. Set the OPENROUTER_API_KEY environment variable."
            )

        import json as _json

        lines = []
        for section_key, entry_name_key in [
            ("experience", "company"),
            ("projects", "name"),
            ("education", "school"),
        ]:
            for entry in profile.get(section_key, []):
                entry_name = entry.get(entry_name_key, "")
                for bullet in entry.get("bullets", []):
                    lines.append(
                        _json.dumps({
                            "section": section_key,
                            "entry": entry_name,
                            "original": bullet,
                        })
                    )

        if not lines:
            logger.warning("tailor_resume — no bullets found in profile")
            return []

        logger.debug("tailor_resume — %d bullets to tailor", len(lines))
        bullets_block = "\n".join(lines)
        user_message = (
            f"Job Description:\n{job_description}\n\n"
            f"Resume Bullets (JSON, one per line):\n{bullets_block}\n\n"
            "For each bullet, write a tailored version that highlights the most relevant "
            "skills and impact for this specific job. "
            "Return a JSON array where each element is: "
            '{"section": <same section>, "entry": <same entry>, '
            '"original": <original text>, "tailored": <new text>}. '
            "Return ONLY the JSON array, no markdown, no explanation."
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
            items = _json.loads(raw)
        except _json.JSONDecodeError:
            logger.error("tailor_resume — JSON parse failed, raw=%r", raw[:500])
            raise ValueError("AI returned unexpected format — please try again.")

        result = [
            {
                "section": item.get("section", ""),
                "entry": item.get("entry", ""),
                "original": item.get("original", ""),
                "tailored": item.get("tailored", ""),
            }
            for item in items
            if item.get("section") in ("experience", "projects", "education")
        ]
        logger.info("tailor_resume — success, %d items returned", len(result))
        return result


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
            '  "core_values": array of 3-6 short strings capturing the company\'s '
            "stated values, mission, or culture pillars.\n"
            '  "recent_projects": array of 3-6 short strings describing recent '
            "products, launches, initiatives, or news mentioned on the site.\n"
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


def save_model_config(fast: str, powerful: str) -> None:
    global _model_config_cache
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    with open(_MODELS_FILE, "w", encoding="utf-8") as f:
        f.write(f"fast={fast.strip()}\n")
        f.write(f"powerful={powerful.strip()}\n")
    _model_config_cache = {"fast": fast.strip(), "powerful": powerful.strip()}


def get_provider(tier: str = "powerful") -> AIProvider:
    """Factory — change this function to swap the AI provider.

    tier: "fast" for cheap/free model (single-bullet rewrites);
          "powerful" for higher-quality model (resume tailoring/generation/research).
    """
    return OpenRouterProvider(tier=tier)
