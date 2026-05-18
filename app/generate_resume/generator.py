from __future__ import annotations

import json
import logging
import pathlib
import re
import shutil
from typing import Any, Callable

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
        self._courses_cache: list[str] | None = None
        self._scored_cache: dict[str, list[dict]] | None = None
        self._filtered_cache: dict[str, Any] | None = None

    # ---------- public API ----------

    def select_courses(self, top_n: int = 10) -> list[str]:
        if self._courses_cache is not None:
            return self._courses_cache
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
        result = select_courses_ai(
            self.provider, all_courses, self.job_description, self.company_research, top_n
        )
        self._courses_cache = result
        return result

    def score_entries(self) -> dict[str, list[dict]]:
        if self._scored_cache is not None:
            return self._scored_cache
        experience = self.profile.get("experience", []) or []
        relevant_exp = [e for e in experience if (e.get("category") or "relevant") == "relevant"]
        leadership = [e for e in experience if (e.get("category") or "relevant") == "other"]
        projects = self.profile.get("projects", []) or []
        awards = self.profile.get("awards", []) or []

        result = {
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
        self._scored_cache = result
        return result

    def build_filtered_profile(self) -> dict[str, Any]:
        if self._filtered_cache is not None:
            return self._filtered_cache
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

        result = {
            "experience": new_experience,
            "projects": ranked_projects,
            "education": new_education,
            "awards": ranked_awards,
            "skills": self.profile.get("skills", []) or [],
            "hobbies": self.profile.get("hobbies", []) or [],
        }
        self._filtered_cache = result
        return result

    def generate_latex(
        self,
        output_pdf: pathlib.Path | str | None = None,
        company: str | None = None,
        progress_cb: Callable[[str], None] | None = None,
        stream_cb: Callable[[str, str], None] | None = None,
    ) -> dict:
        """Generate, compile, and grade the resume.

        Returns {"latex": str, "pdf": Path | None, "pages": int | None,
                 "grade": {"score": float, "feedback": str} | None}.
        If `output_pdf` is provided, the PDF is written there. Otherwise it goes to
        `<resume_output_dir>/<slug(company)>_resume.pdf` (or `resume.pdf` if no company).

        `progress_cb(msg)` receives attempt-boundary status strings.
        `stream_cb(stage, chunk)` receives streamed LLM token chunks where
        `stage` is one of "tailor", "generate", "grade".
        """
        filtered_base = self.build_filtered_profile()
        filtered = self._tailor_profile_bullets(filtered_base, stream_cb=stream_cb)

        page_cap = get_resume_page_cap()
        writer_feedback: str | None = None
        bullet_feedback: str | None = None
        attempts: list[dict] = []

        for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
            logger.info("generate_latex — attempt %d/%d", attempt, MAX_GENERATION_ATTEMPTS)
            if bullet_feedback is not None:
                if progress_cb:
                    progress_cb(f"Attempt {attempt}: re-tailoring bullets…")
                filtered = self._tailor_profile_bullets(
                    filtered_base, stream_cb=stream_cb, feedback=bullet_feedback
                )
            if progress_cb:
                progress_cb(f"Attempt {attempt}/{MAX_GENERATION_ATTEMPTS}: generating LaTeX…")
            try:
                latex = self._generate_resume_text(filtered, writer_feedback, stream_cb)
            except Exception:
                logger.exception("generate_latex — provider.generate_resume failed on attempt %d", attempt)
                raise

            pages: int | None = None
            compile_error: str | None = None
            pdf_path: pathlib.Path | None = None
            if progress_cb:
                progress_cb(f"Attempt {attempt}: compiling LaTeX…")
            try:
                pdf_path = compile_latex(latex)
                pages = pdf_page_count(pdf_path)
            except LatexCompileError as e:
                compile_error = f"{e}\n{e.log_excerpt}".strip()
                logger.warning("generate_latex — attempt %d compile failed: %s", attempt, e)

            grade: dict | None = None
            if compile_error is None:
                if progress_cb:
                    progress_cb(f"Attempt {attempt}: grading…")
                try:
                    grade = self._grade_resume_text(latex, stream_cb)
                except Exception:
                    logger.exception("generate_latex — grade_resume failed on attempt %d", attempt)
                    raise
                if progress_cb and grade is not None:
                    progress_cb(
                        f"Attempt {attempt}: graded {grade['score']:.2f}/10"
                    )

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

            writer_parts: list[str] = []
            if compile_error:
                writer_parts.append(
                    "PREVIOUS DRAFT FAILED TO COMPILE. Fix the LaTeX syntax. "
                    f"Compiler output:\n{compile_error}"
                )
            if pages is not None and not page_ok:
                writer_parts.append(
                    f"PREVIOUS DRAFT WAS {pages} PAGES; it MUST fit on {page_cap}. "
                    "Tighten margins/spacing, trim the weakest entries, or drop optional "
                    "sections. Do NOT rewrite bullet text."
                )
            writer_feedback = "\n\n".join(writer_parts) if writer_parts else None
            bullet_feedback = (
                grade["feedback"] if (grade is not None and not score_ok) else None
            )

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

    def _tailor_profile_bullets(
        self,
        profile: dict[str, Any],
        stream_cb: Callable[[str, str], None] | None = None,
        feedback: str | None = None,
    ) -> dict[str, Any]:
        out = dict(profile)
        sections = ("experience", "projects", "awards")

        all_bullets: list[str] = []
        slices: list[tuple[str, int, int, int]] = []
        for section in sections:
            entries = out.get(section) or []
            for idx, entry in enumerate(entries):
                bullets = list(entry.get("bullets", []) or [])
                if not bullets:
                    continue
                start = len(all_bullets)
                all_bullets.extend(bullets)
                slices.append((section, idx, start, start + len(bullets)))

        if not all_bullets:
            return out

        try:
            tailored = self._tailor_bullets_text(all_bullets, stream_cb, feedback)
        except Exception:
            logger.exception(
                "_tailor_profile_bullets — tailor_bullets failed; keeping originals"
            )
            return out

        if len(tailored) != len(all_bullets):
            logger.error(
                "_tailor_profile_bullets — length mismatch: sent %d, got %d; keeping originals",
                len(all_bullets),
                len(tailored),
            )
            return out

        section_entries: dict[str, list[dict]] = {
            section: list(out.get(section) or []) for section in sections
        }
        for section, idx, start, end in slices:
            entry = section_entries[section][idx]
            section_entries[section][idx] = {**entry, "bullets": tailored[start:end]}
        for section in sections:
            out[section] = section_entries[section]
        return out

    def _tailor_bullets_text(
        self,
        bullets: list[str],
        stream_cb: Callable[[str, str], None] | None,
        feedback: str | None = None,
    ) -> list[str]:
        if stream_cb is None:
            return self.provider.tailor_bullets(bullets, self.job_description, feedback)

        raw_parts: list[str] = []
        for chunk in self.provider.tailor_bullets_stream(bullets, self.job_description, feedback):
            raw_parts.append(chunk)
            stream_cb("tailor", chunk)
        raw = "".join(raw_parts).strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("_tailor_bullets_text — JSON parse failed, raw=%r", raw[:500])
            raise ValueError("AI returned unexpected format — please try again.")
        if not isinstance(items, list) or not all(isinstance(s, str) for s in items):
            raise ValueError("AI returned unexpected format — please try again.")
        if len(items) != len(bullets):
            raise ValueError("AI returned unexpected format — please try again.")
        return items

    def _generate_resume_text(
        self,
        filtered: dict,
        feedback: str | None,
        stream_cb: Callable[[str, str], None] | None,
    ) -> str:
        if stream_cb is None:
            return self.provider.generate_resume(
                filtered, self.job_description, feedback=feedback
            )
        raw_parts: list[str] = []
        for chunk in self.provider.generate_resume_stream(
            filtered, self.job_description, feedback=feedback
        ):
            raw_parts.append(chunk)
            stream_cb("generate", chunk)
        raw = "".join(raw_parts).strip()
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

    def _grade_resume_text(
        self,
        latex: str,
        stream_cb: Callable[[str, str], None] | None,
    ) -> dict:
        if stream_cb is None:
            return self.provider.grade_resume(latex, self.job_description)
        raw_parts: list[str] = []
        for chunk in self.provider.grade_resume_stream(latex, self.job_description):
            raw_parts.append(chunk)
            stream_cb("grade", chunk)
        raw = "".join(raw_parts).strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("_grade_resume_text — JSON parse failed, raw=%r", raw[:500])
            raise ValueError("AI returned unexpected format — please try again.")
        if not isinstance(obj, dict) or "score" not in obj or "feedback" not in obj:
            raise ValueError("AI returned unexpected format — please try again.")
        try:
            score = float(obj["score"])
        except (TypeError, ValueError):
            raise ValueError("AI returned unexpected format — please try again.")
        return {"score": score, "feedback": str(obj["feedback"])}

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
