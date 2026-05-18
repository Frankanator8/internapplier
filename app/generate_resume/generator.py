from __future__ import annotations

import logging
from typing import Any

from app.ai_provider import AIProvider, OpenRouterProvider, get_provider

from .date_utils import parse_date, recency_score
from .scoring import combine_score, score_entries_ai, select_courses_ai

logger = logging.getLogger(__name__)


class ResumeGenerator:
    def __init__(
        self,
        profile: dict,
        job_description: str,
        company_research: dict | None,
        provider: AIProvider | None = None,
    ):
        self.profile = profile or {}
        self.job_description = job_description or ""
        self.company_research = company_research or {}
        self.provider: OpenRouterProvider = provider or get_provider()  # type: ignore[assignment]

    # ---------- public API ----------

    def select_courses(self, top_n: int = 10) -> list[str]:
        all_courses: list[str] = []
        seen: set[str] = set()
        for edu in self.profile.get("education", []) or []:
            for c in edu.get("courses", []) or []:
                c = str(c).strip()
                key = c.lower()
                if c and key not in seen:
                    seen.add(key)
                    all_courses.append(c)
        logger.info("select_courses — %d unique courses, top_n=%d", len(all_courses), top_n)
        return select_courses_ai(
            self.provider, all_courses, self.job_description, self.company_research, top_n
        )

    def score_entries(self) -> dict[str, list[dict]]:
        experience = self.profile.get("experience", []) or []
        relevant_exp = [e for e in experience if (e.get("category") or "relevant") == "relevant"]
        leadership = [e for e in experience if (e.get("category") or "relevant") == "other"]
        projects = self.profile.get("projects", []) or []
        awards = self.profile.get("awards", []) or []

        return {
            "relevant_experience": self._score_section(
                relevant_exp, _exp_label, _exp_date, include_relevancy=True
            ),
            "projects": self._score_section(
                projects, _project_label, _project_date, include_relevancy=True
            ),
            "awards": self._score_section(
                awards, _award_label, _award_date, include_relevancy=True
            ),
            "leadership": self._score_section(
                leadership, _exp_label, _exp_date, include_relevancy=False
            ),
        }

    def build_filtered_profile(self) -> dict[str, Any]:
        scored = self.score_entries()
        courses = self.select_courses(10)

        ranked_relevant = [r["entry"] for r in scored["relevant_experience"]]
        ranked_leadership = [r["entry"] for r in scored["leadership"]]
        ranked_projects = [r["entry"] for r in scored["projects"]]
        ranked_awards = [r["entry"] for r in scored["awards"]]

        # rebuild experience list: relevant first (ranked), then leadership (ranked)
        new_experience = ranked_relevant + ranked_leadership

        new_education = []
        for edu in self.profile.get("education", []) or []:
            edu_copy = dict(edu)
            existing = {str(c).strip().lower() for c in edu_copy.get("courses", []) or []}
            edu_copy["courses"] = [c for c in courses if c.strip().lower() in existing]
            new_education.append(edu_copy)

        return {
            "experience": new_experience,
            "projects": ranked_projects,
            "education": new_education,
            "awards": ranked_awards,
            "skills": self.profile.get("skills", []) or [],
            "hobbies": self.profile.get("hobbies", []) or [],
        }

    def generate_latex(self) -> str:
        filtered = self.build_filtered_profile()
        return self.provider.generate_resume(filtered, self.job_description)

    # ---------- internals ----------

    def _score_section(
        self,
        entries: list[dict],
        label_fn,
        date_fn,
        *,
        include_relevancy: bool,
    ) -> list[dict]:
        if not entries:
            return []
        pairs = [(label_fn(e), list(e.get("bullets", []) or [])) for e in entries]
        ai_scores = score_entries_ai(
            self.provider,
            pairs,
            self.job_description,
            self.company_research,
            include_relevancy=include_relevancy,
        )

        results: list[dict] = []
        for entry, ai in zip(entries, ai_scores):
            keys = ("impact", "prestige", "relevancy") if include_relevancy else ("impact", "prestige")
            ai_avg = sum(ai[k] for k in keys) / len(keys)
            rec = recency_score(parse_date(date_fn(entry)))
            final = combine_score(ai_avg, rec)
            results.append({
                "entry": entry,
                "label": label_fn(entry),
                "ai": ai,
                "recency": rec,
                "final_score": final,
            })
        results.sort(key=lambda r: r["final_score"], reverse=True)
        return results


# ---------- label / date helpers ----------

def _exp_label(e: dict) -> str:
    role = (e.get("role") or "").strip()
    company = (e.get("company") or "").strip()
    if role and company:
        return f"{role} @ {company}"
    return role or company or "(unnamed experience)"


def _exp_date(e: dict) -> str | None:
    return e.get("end") or e.get("start")


def _project_label(p: dict) -> str:
    return (p.get("name") or "(unnamed project)").strip()


def _project_date(p: dict) -> str | None:
    return p.get("end") or p.get("start") or p.get("date")


def _award_label(a: dict) -> str:
    title = (a.get("title") or "").strip()
    issuer = (a.get("issuer") or "").strip()
    if title and issuer:
        return f"{title} — {issuer}"
    return title or issuer or "(unnamed award)"


def _award_date(a: dict) -> str | None:
    return a.get("date")
