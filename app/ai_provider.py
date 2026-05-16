import os
from abc import ABC, abstractmethod

import requests


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


class OpenRouterProvider(AIProvider):
    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
    DEFAULT_MODEL = "openai/gpt-4o-mini"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.model = model or self.DEFAULT_MODEL

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


def get_provider() -> AIProvider:
    """Factory — change this function to swap the AI provider."""
    return OpenRouterProvider()
