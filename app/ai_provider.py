import os
import pathlib
from abc import ABC, abstractmethod

import requests


_APP_DIR = pathlib.Path.home() / "Library" / "Application Support" / "InternApplier"
_MODELS_FILE = _APP_DIR / "models.txt"

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

    def analyze_bullet(self, bullet: str, context: dict) -> str:
        if not self.api_key:
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
                        "content": (
                            "You are an expert resume coach helping candidates "
                            "write strong, impact-driven resume bullet points. "
                            "Be concise and specific."
                        ),
                    },
                    {"role": "user", "content": user_message},
                ],
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def tailor_resume(self, profile: dict, job_description: str) -> list[dict]:
        if not self.api_key:
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
            return []

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
                        "content": (
                            "You are an expert resume coach. Given a job description "
                            "and a candidate's resume bullets, rewrite each bullet to "
                            "better match the role. Be specific, use strong action verbs, "
                            "and emphasize relevant impact."
                        ),
                    },
                    {"role": "user", "content": user_message},
                ],
            },
            timeout=60,
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"].strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            items = _json.loads(raw)
        except _json.JSONDecodeError:
            raise ValueError("AI returned unexpected format — please try again.")

        return [
            {
                "section": item.get("section", ""),
                "entry": item.get("entry", ""),
                "original": item.get("original", ""),
                "tailored": item.get("tailored", ""),
            }
            for item in items
            if item.get("section") in ("experience", "projects", "education")
        ]


    def generate_resume(self, profile: dict, job_description: str) -> str:
        if not self.api_key:
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
                        "content": (
                            "You are an expert resume writer who outputs only "
                            "compilable LaTeX source. Never include commentary "
                            "or markdown fences."
                        ),
                    },
                    {"role": "user", "content": user_message},
                ],
            },
            timeout=90,
        )
        response.raise_for_status()
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

        return raw


    def research_company(self, company_name: str, scraped_text: str) -> dict:
        if not self.api_key:
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
                        "content": (
                            "You are a career-prep assistant. Summarize companies "
                            "concisely and faithfully from provided source text. "
                            "Do not invent facts not present in the source."
                        ),
                    },
                    {"role": "user", "content": user_message},
                ],
            },
            timeout=60,
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"].strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            data = _json.loads(raw)
        except _json.JSONDecodeError:
            raise ValueError("AI returned unexpected format — please try again.")

        def _str_list(v) -> list[str]:
            if not isinstance(v, list):
                return []
            return [str(x).strip() for x in v if str(x).strip()]

        return {
            "core_values": _str_list(data.get("core_values")),
            "recent_projects": _str_list(data.get("recent_projects")),
            "summary": str(data.get("summary", "")).strip(),
        }


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
