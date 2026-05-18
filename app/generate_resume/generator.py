from __future__ import annotations

import logging
import pathlib
import re
import shutil
from typing import Any

from app.ai_provider import (
    AIProvider,
    OpenRouterProvider,
    get_provider,
    get_resume_output_dir,
    get_resume_page_cap,
)

from .compile import LatexCompileError, compile_latex, pdf_page_count
from .date_utils import parse_date, recency_score
from .scoring import combine_score, score_entries_ai, select_courses_ai

MAX_GENERATION_ATTEMPTS = 4
SCORE_THRESHOLD = 9.5

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

    def generate_latex(
        self,
        output_pdf: pathlib.Path | str | None = None,
        company: str | None = None,
    ) -> dict:
        """Generate, compile, and grade the resume.

        Returns {"latex": str, "pdf": Path | None, "pages": int | None,
                 "grade": {"score": float, "feedback": str} | None}.
        If `output_pdf` is provided, the PDF is written there. Otherwise it goes to
        `<resume_output_dir>/<slug(company)>_resume.pdf` (or `resume.pdf` if no company).
        """
        filtered = self.build_filtered_profile()
        filtered = self._tailor_profile_bullets(filtered)

        page_cap = get_resume_page_cap()
        feedback: str | None = None
        attempts: list[dict] = []

        for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
            logger.info("generate_latex — attempt %d/%d", attempt, MAX_GENERATION_ATTEMPTS)
            try:
                latex = self.provider.generate_resume(
                    filtered, self.job_description, feedback=feedback
                )
            except Exception:
                logger.exception("generate_latex — provider.generate_resume failed on attempt %d", attempt)
                raise

            pages: int | None = None
            compile_error: str | None = None
            pdf_path: pathlib.Path | None = None
            try:
                pdf_path = compile_latex(latex)
                pages = pdf_page_count(pdf_path)
            except LatexCompileError as e:
                compile_error = f"{e}\n{e.log_excerpt}".strip()
                logger.warning("generate_latex — attempt %d compile failed: %s", attempt, e)

            grade: dict | None = None
            if compile_error is None:
                try:
                    grade = self.provider.grade_resume(latex, self.job_description)
                except Exception:
                    logger.exception("generate_latex — grade_resume failed on attempt %d", attempt)
                    raise

            page_ok = pages is not None and pages <= page_cap
            score_ok = grade is not None and grade["score"] >= SCORE_THRESHOLD

            attempts.append({
                "latex": latex,
                "pdf": pdf_path,
                "pages": pages,
                "grade": grade,
                "compile_error": compile_error,
            })
            logger.info(
                "generate_latex — attempt %d: pages=%s score=%s compiled=%s",
                attempt,
                pages,
                grade["score"] if grade else None,
                compile_error is None,
            )

            if page_ok and score_ok:
                logger.info("generate_latex — passed on attempt %d", attempt)
                final_pdf = _persist_pdf(pdf_path, output_pdf, company)
                return {"latex": latex, "pdf": final_pdf, "pages": pages, "grade": grade}

            parts: list[str] = []
            if compile_error:
                parts.append(
                    "PREVIOUS DRAFT FAILED TO COMPILE. Fix the LaTeX syntax. "
                    f"Compiler output:\n{compile_error}"
                )
            if pages is not None and not page_ok:
                parts.append(
                    f"PREVIOUS DRAFT WAS {pages} PAGES; it MUST fit on {page_cap}. "
                    "Cut the weakest bullets, shorten phrasing, tighten margins/spacing if needed."
                )
            if grade is not None and not score_ok:
                parts.append(
                    f"Grader scored {grade['score']:.2f}/10 (need ≥ {SCORE_THRESHOLD}). "
                    f"Address this feedback:\n{grade['feedback']}"
                )
            feedback = "\n\n".join(parts) if parts else None

        best = self._pick_best_attempt(attempts, page_cap)
        logger.warning(
            "generate_latex — exhausted %d attempts; returning best (pages=%s, score=%s)",
            MAX_GENERATION_ATTEMPTS,
            best.get("pages"),
            best["grade"]["score"] if best.get("grade") else None,
        )
        final_pdf = _persist_pdf(best.get("pdf"), output_pdf, company)
        return {
            "latex": best["latex"],
            "pdf": final_pdf,
            "pages": best.get("pages"),
            "grade": best.get("grade"),
        }

    def _tailor_profile_bullets(self, profile: dict[str, Any]) -> dict[str, Any]:
        out = dict(profile)
        for section in ("experience", "projects", "awards"):
            entries = out.get(section) or []
            new_entries = []
            for entry in entries:
                bullets = list(entry.get("bullets", []) or [])
                if bullets:
                    try:
                        tailored = self.provider.tailor_resume(bullets, self.job_description)
                        entry = {**entry, "bullets": tailored}
                    except Exception:
                        logger.exception(
                            "_tailor_profile_bullets — tailor_resume failed for section=%s; keeping originals",
                            section,
                        )
                new_entries.append(entry)
            out[section] = new_entries
        return out

    @staticmethod
    def _pick_best_attempt(attempts: list[dict], page_cap: int) -> dict:
        def key(a: dict) -> tuple:
            compiled = a.get("compile_error") is None
            page_ok = a.get("pages") is not None and a["pages"] <= page_cap
            score = a["grade"]["score"] if a.get("grade") else -1.0
            return (compiled, page_ok, score)

        return max(attempts, key=key)

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
        triples = [
            (label_fn(e), _date_display(e), list(e.get("bullets", []) or []))
            for e in entries
        ]
        ai_scores = score_entries_ai(
            self.provider,
            triples,
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


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _persist_pdf(
    src: pathlib.Path | None,
    dest: pathlib.Path | str | None,
    company: str | None = None,
) -> pathlib.Path | None:
    if src is None or not src.exists():
        return None
    if dest:
        target = pathlib.Path(dest)
    else:
        slug = _slugify(company) if company else ""
        name = f"{slug}_resume.pdf" if slug else "resume.pdf"
        target = get_resume_output_dir() / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, target)
    logger.info("generate_latex — PDF written to %s", target)
    return target


# ---------- label / date helpers ----------

def _date_display(entry: dict) -> str:
    start = (entry.get("start") or "").strip()
    end = (entry.get("end") or "").strip()
    single = (entry.get("date") or "").strip()
    if start and end:
        return f"{start} – {end}"
    return end or start or single or ""


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
