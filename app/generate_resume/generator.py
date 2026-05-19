from __future__ import annotations

import json
import logging
import pathlib
import re
import shutil
from typing import Any, Callable

from app.ai_provider import (
    OpenRouterProvider,
    get_max_generation_attempts,
    get_max_latex_fix_attempts,
    get_provider,
    get_resume_output_dir,
    get_resume_page_cap,
)

from .compile import LatexCompileError, compile_latex, pdf_page_count
from .date_utils import parse_date, recency_score
from .scoring import combine_score, score_entries_ai, select_courses_ai

SCORE_THRESHOLD = 9.5

logger = logging.getLogger(__name__)


def _emit(stream_cb: Callable[[str, str], None] | None, stage: str, text: str) -> None:
    print(text, flush=True)
    if stream_cb is not None:
        stream_cb(stage, text + "\n")


def _collect_stream(
    stage: str,
    chunks,
    stream_cb: Callable[[str, str], None] | None,
) -> str:
    parts: list[str] = []
    for chunk in chunks:
        parts.append(chunk)
        if stream_cb is not None:
            stream_cb(stage, chunk)
    return "".join(parts).strip()


def _strip_code_fence(raw: str, lang_hints: tuple[str, ...] = ()) -> str:
    raw = raw.strip()
    for hint in lang_hints:
        pattern = re.compile(
            r"```" + re.escape(hint) + r"[ \t]*\r?\n(.*?)```",
            re.DOTALL | re.IGNORECASE,
        )
        m = pattern.search(raw)
        if m:
            return m.group(1).strip()
    m = re.search(r"```[a-zA-Z0-9_+-]*[ \t]*\r?\n(.*?)```", raw, re.DOTALL)
    if m:
        return m.group(1).strip()
    return raw


class ResumeGenerator:
    def __init__(
        self,
        profile: dict,
        job_description: str,
        company_research: dict | None,
        provider: OpenRouterProvider | None = None,
    ):
        self.profile = profile or {}
        self.job_description = job_description or ""
        self.company_research = company_research or {}
        self.provider: OpenRouterProvider = provider or get_provider()
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

    def score_entries(
        self,
        stream_cb: Callable[[str, str], None] | None = None,
    ) -> dict[str, list[dict]]:
        if self._scored_cache is not None:
            return self._scored_cache
        experience = self.profile.get("experience", []) or []
        relevant_exp = [e for e in experience if (e.get("category") or "relevant") == "relevant"]
        leadership = [e for e in experience if (e.get("category") or "relevant") == "other"]
        projects = self.profile.get("projects", []) or []
        awards = self.profile.get("awards", []) or []

        result = {
            "relevant_experience": self._score_section(
                relevant_exp, _exp_label, _exp_date,
                include_relevancy=True, section_name="relevant_experience",
                stream_cb=stream_cb,
            ),
            "projects": self._score_section(
                projects, _project_label, _project_date,
                include_relevancy=True, section_name="projects",
                stream_cb=stream_cb,
            ),
            "awards": self._score_section(
                awards, _award_label, _award_date,
                include_relevancy=True, section_name="awards",
                stream_cb=stream_cb,
            ),
            "leadership": self._score_section(
                leadership, _exp_label, _exp_date,
                include_relevancy=False, section_name="leadership",
                stream_cb=stream_cb,
            ),
        }
        self._scored_cache = result
        return result

    def build_filtered_profile(
        self,
        stream_cb: Callable[[str, str], None] | None = None,
    ) -> dict[str, Any]:
        if self._filtered_cache is not None:
            return self._filtered_cache
        scored = self.score_entries(stream_cb=stream_cb)
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
                 "grade": {"score": float, "bullet_feedback": str, "writer_feedback": str} | None}.
        If `output_pdf` is provided, the PDF is written there. Otherwise it goes to
        `<resume_output_dir>/<slug(company)>_resume.pdf` (or `resume.pdf` if no company).

        `progress_cb(msg)` receives attempt-boundary status strings.
        `stream_cb(stage, chunk)` receives streamed LLM token chunks where
        `stage` is one of "tailor", "generate", "grade".
        """
        filtered_base = self.build_filtered_profile(stream_cb=stream_cb)
        trim_queue = self._build_trim_queue()  # ascending by final_score
        omitted_entries: set[int] = set()
        dropped_labels: list[str] = []

        page_cap = get_resume_page_cap()
        max_attempts = get_max_generation_attempts()
        writer_feedback: str | None = None
        bullet_feedback: str | None = None
        attempts: list[dict] = []

        if progress_cb:
            progress_cb("Tailoring bullets…")
        filtered = self._tailor_profile_bullets(
            filtered_base, stream_cb=stream_cb, feedback=None
        )

        for attempt in range(1, max_attempts + 1):
            logger.info("generate_latex — attempt %d/%d", attempt, max_attempts)
            if bullet_feedback:
                if progress_cb:
                    progress_cb(f"Attempt {attempt}: re-tailoring bullets…")
                filtered = self._tailor_profile_bullets(
                    filtered, stream_cb=stream_cb, feedback=bullet_feedback
                )
            filtered = self._apply_omissions(filtered, omitted_entries)
            if logger.isEnabledFor(logging.DEBUG):
                first_bullet = _first_bullet(filtered)
                logger.debug(
                    "generate_latex — attempt %d first bullet: %r",
                    attempt, (first_bullet or "")[:140],
                )
            if progress_cb:
                progress_cb(f"Attempt {attempt}/{max_attempts}: generating LaTeX…")
            previous_latex = attempts[-1]["latex"] if attempts else None
            try:
                latex = self._generate_resume_text(
                    filtered, writer_feedback, previous_latex, stream_cb
                )
            except Exception:
                logger.exception("generate_latex — provider.generate_resume failed on attempt %d", attempt)
                raise

            if progress_cb:
                progress_cb(f"Attempt {attempt}: compiling LaTeX…")
            latex, pdf_path, compile_error = self._compile_with_fix(
                latex, attempt, progress_cb, stream_cb
            )
            pages = pdf_page_count(pdf_path) if pdf_path is not None else None

            grade: dict | None = None
            if progress_cb:
                progress_cb(f"Attempt {attempt}: grading…")
            try:
                grade = self._grade_resume_text(latex, stream_cb)
            except Exception:
                logger.exception("generate_latex — grade_resume failed on attempt %d", attempt)
                grade = None
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
                "attempt": attempt,
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
                return {
                    "latex": latex,
                    "pdf": final_pdf,
                    "pages": pages,
                    "grade": grade,
                    "attempts": _attempts_summary(attempts),
                    "chosen_attempt": attempt,
                }

            if pages is not None and not page_ok:
                self._drop_one_from_trim_queue(
                    trim_queue, omitted_entries, dropped_labels, pages, page_cap
                )

            writer_feedback = _build_writer_feedback(
                compile_error, pages, page_ok, page_cap, grade, score_ok
            )
            bullet_feedback = _build_bullet_feedback(
                pages, page_ok, page_cap, dropped_labels, grade, score_ok
            )

        best = self._pick_best_attempt(attempts, page_cap)
        logger.warning(
            "generate_latex — exhausted %d attempts; returning best (pages=%s, score=%s)",
            max_attempts,
            best.get("pages"),
            best["grade"]["score"] if best.get("grade") else None,
        )
        final_pdf = _persist_pdf(best.get("pdf"), output_pdf, company)
        return {
            "latex": best["latex"],
            "pdf": final_pdf,
            "pages": best.get("pages"),
            "grade": best.get("grade"),
            "attempts": _attempts_summary(attempts),
            "chosen_attempt": best.get("attempt"),
        }

    def _build_trim_queue(self) -> list[dict]:
        """All scored entries sorted ascending by final_score.

        The orchestrator pops from the front of this queue to free space when
        the rendered draft exceeds the page cap. Each item is
        {entry, label, final_score, section}.
        """
        scored = self.score_entries()
        pool: list[dict] = []
        for section_key, label_fn in (
            ("relevant_experience", _exp_label),
            ("projects", _project_label),
            ("leadership", _exp_label),
            ("awards", _award_label),
        ):
            for r in scored.get(section_key, []) or []:
                pool.append({
                    "entry": r["entry"],
                    "label": r.get("label") or label_fn(r["entry"]),
                    "final_score": r["final_score"],
                    "section": section_key,
                })
        pool.sort(key=lambda r: r["final_score"])
        return pool

    @staticmethod
    def _drop_one_from_trim_queue(
        trim_queue: list[dict],
        omitted_entries: set[int],
        dropped_labels: list[str],
        pages: int,
        page_cap: int,
    ) -> bool:
        while trim_queue:
            victim = trim_queue.pop(0)
            if id(victim["entry"]) in omitted_entries:
                continue
            omitted_entries.add(id(victim["entry"]))
            dropped_labels.append(f"{victim['label']} (entry)")
            logger.info(
                "generate_latex — page overflow (%d > %d), dropping entry %s "
                "from trim_queue (score=%.3f)",
                pages, page_cap, victim["label"], victim["final_score"],
            )
            return True
        return False

    @staticmethod
    def _apply_omissions(
        filtered_base: dict,
        omitted_entries: set[int],
    ) -> dict:
        out = {k: (list(v) if isinstance(v, list) else v) for k, v in filtered_base.items()}
        if not omitted_entries:
            return out
        for section in ("experience", "projects", "awards"):
            entries = filtered_base.get(section) or []
            out[section] = [e for e in entries if id(e) not in omitted_entries]
        return out

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
        raw = _strip_code_fence(
            _collect_stream(
                "tailor",
                self.provider.tailor_bullets_stream(bullets, self.job_description, feedback),
                stream_cb,
            ),
            lang_hints=("json",),
        )
        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("_tailor_bullets_text — JSON parse failed, raw=%r", raw[:500])
            raise ValueError("AI returned unexpected format — please try again.")
        if not isinstance(items, list) or not all(isinstance(s, str) for s in items):
            logger.error(
                "_tailor_bullets_text — not a list[str]; type=%s sample=%r",
                type(items).__name__, repr(items)[:500],
            )
            raise ValueError("AI returned unexpected format — please try again.")
        if len(items) != len(bullets):
            logger.error(
                "_tailor_bullets_text — length mismatch: sent %d, got %d",
                len(bullets), len(items),
            )
            raise ValueError("AI returned unexpected format — please try again.")
        return items

    def _generate_resume_text(
        self,
        filtered: dict,
        feedback: str | None,
        previous_latex: str | None,
        stream_cb: Callable[[str, str], None] | None,
    ) -> str:
        return _strip_code_fence(
            _collect_stream(
                "generate",
                self.provider.generate_resume_stream(
                    filtered, self.job_description, feedback=feedback,
                    previous_latex=previous_latex,
                ),
                stream_cb,
            ),
            lang_hints=("latex", "tex"),
        )

    def _compile_with_fix(
        self,
        latex: str,
        attempt: int,
        progress_cb: Callable[[str], None] | None,
        stream_cb: Callable[[str, str], None] | None,
    ) -> tuple[str, pathlib.Path | None, str | None]:
        try:
            return latex, compile_latex(latex), None
        except LatexCompileError as e:
            compile_error = f"{e}\n{e.log_excerpt}".strip()

        max_fix = get_max_latex_fix_attempts()
        last_error_signature: str | None = None
        for fix_idx in range(1, max_fix + 1):
            logger.warning(
                "generate_latex — attempt %d compile failed; latex-fixer pass %d/%d",
                attempt, fix_idx, max_fix,
            )
            _emit(
                stream_cb,
                "fix-latex",
                f"[fix-latex] attempt {attempt} pass {fix_idx}/{max_fix}: "
                f"repairing LaTeX\n{compile_error}",
            )
            if progress_cb:
                progress_cb(
                    f"Attempt {attempt}: fixing LaTeX (pass {fix_idx}/{max_fix})…"
                )

            try:
                fixed = self._fix_latex_text(latex, compile_error, stream_cb)
            except Exception:
                logger.exception(
                    "_compile_with_fix — fixer failed on attempt %d pass %d",
                    attempt, fix_idx,
                )
                break

            if not fixed or fixed == latex:
                logger.info(
                    "_compile_with_fix — fixer returned no change; aborting repair loop"
                )
                break
            latex = fixed

            try:
                return latex, compile_latex(latex), None
            except LatexCompileError as e:
                new_error = f"{e}\n{e.log_excerpt}".strip()
                signature = str(e)
                if signature == last_error_signature:
                    logger.info(
                        "_compile_with_fix — same error after fix; aborting repair loop"
                    )
                    compile_error = new_error
                    break
                last_error_signature = signature
                compile_error = new_error

        _emit(
            stream_cb,
            "compile-error",
            f"[compile-error] attempt {attempt}: LaTeX failed to compile after fixer "
            f"— grading raw LaTeX anyway\n{compile_error}",
        )
        if progress_cb:
            progress_cb(f"Attempt {attempt}: compile failed — grading anyway")
        return latex, None, compile_error

    def _fix_latex_text(
        self,
        latex: str,
        compile_error: str,
        stream_cb: Callable[[str, str], None] | None,
    ) -> str:
        return _strip_code_fence(
            _collect_stream(
                "fix-latex",
                self.provider.fix_latex_stream(latex, compile_error),
                stream_cb,
            ),
            lang_hints=("latex", "tex"),
        )

    def _grade_resume_text(
        self,
        latex: str,
        stream_cb: Callable[[str, str], None] | None,
    ) -> dict:
        raw = _strip_code_fence(
            _collect_stream(
                "grade",
                self.provider.grade_resume_stream(latex, self.job_description),
                stream_cb,
            ),
            lang_hints=("json",),
        )
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("_grade_resume_text — JSON parse failed, raw=%r", raw[:500])
            raise ValueError("AI returned unexpected format — please try again.")
        required = ("score", "bullet_feedback", "writer_feedback")
        if not isinstance(obj, dict) or not all(k in obj for k in required):
            logger.error(
                "_grade_resume_text — schema mismatch; type=%s keys=%r raw=%r",
                type(obj).__name__,
                list(obj.keys()) if isinstance(obj, dict) else None,
                raw[:1000],
            )
            raise ValueError("AI returned unexpected format — please try again.")
        try:
            score = float(obj["score"])
        except (TypeError, ValueError):
            logger.error(
                "_grade_resume_text — score not numeric: %r", obj.get("score")
            )
            raise ValueError("AI returned unexpected format — please try again.")

        result = {
            "score": score,
            "bullet_feedback": str(obj["bullet_feedback"]),
            "writer_feedback": str(obj["writer_feedback"]),
        }

        def _indent(text: str, prefix: str = "    ") -> str:
            return "\n".join(prefix + ln for ln in (text or "").splitlines()) or (prefix + "(empty)")

        lines = [f"[grader] score={score:.2f}/10"]
        lines.append("  writer_feedback:")
        lines.append(_indent(result["writer_feedback"]))
        lines.append("  bullet_feedback:")
        lines.append(_indent(result["bullet_feedback"]))
        _emit(stream_cb, "grade-result", "\n".join(lines))

        return result

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
        section_name: str = "",
        stream_cb: Callable[[str, str], None] | None = None,
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

        lines = [f"[scores] {section_name or '(section)'}"]
        for i, r in enumerate(results, start=1):
            ai = r["ai"]
            if include_relevancy:
                ai_str = (
                    f"impact={ai.get('impact')} prestige={ai.get('prestige')} "
                    f"relevancy={ai.get('relevancy')}"
                )
            else:
                ai_str = f"impact={ai.get('impact')} prestige={ai.get('prestige')}"
            lines.append(f"  {i}. {r['label']}")
            lines.append(
                f"     ai: {ai_str}  recency={r['recency']:.2f}  final={r['final_score']:.3f}"
            )
        _emit(stream_cb, "scores", "\n".join(lines))

        return results


def _build_writer_feedback(
    compile_error: str | None,
    pages: int | None,
    page_ok: bool,
    page_cap: int,
    grade: dict | None,
    score_ok: bool,
) -> str | None:
    parts: list[str] = []
    if compile_error:
        parts.append(
            "PREVIOUS DRAFT FAILED TO COMPILE. Fix the LaTeX syntax. "
            f"Compiler output:\n{compile_error}"
        )
    if pages is not None and not page_ok:
        parts.append(
            f"PREVIOUS DRAFT WAS {pages} PAGES; it MUST fit on {page_cap}. "
            "Tighten margins/spacing if possible. The profile and bullets have "
            "already been trimmed by the orchestrator."
        )
    if grade is not None and not score_ok and grade.get("writer_feedback"):
        parts.append(
            "GRADER FEEDBACK (resume choice — section ordering, skills, layout):\n"
            + grade["writer_feedback"]
        )
    return "\n\n".join(parts) if parts else None


def _build_bullet_feedback(
    pages: int | None,
    page_ok: bool,
    page_cap: int,
    dropped_labels: list[str],
    grade: dict | None,
    score_ok: bool,
) -> str | None:
    parts: list[str] = []
    if pages is not None and not page_ok:
        drop_note = (
            f"Drops applied so far to free space: {'; '.join(dropped_labels)}."
            if dropped_labels
            else "No content could be dropped (all remaining is essential)."
        )
        parts.append(
            f"PAGE OVERFLOW: previous draft was {pages} pages; the resume MUST fit on "
            f"{page_cap}. {drop_note} Shorten the remaining bullets where you can. "
            "Length may drop below the original — but keep the most important "
            "information (lead action verb, primary impact metric, key tools relevant "
            "to the JD); drop secondary clauses first. Never invent facts."
        )
    if grade is not None and not score_ok and grade.get("bullet_feedback"):
        parts.append(
            "GRADER FEEDBACK (improve bullet content/wording):\n"
            + grade["bullet_feedback"]
        )
    return "\n\n".join(parts) if parts else None


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _attempts_summary(attempts: list[dict]) -> list[dict]:
    out: list[dict] = []
    for a in attempts:
        pdf = a.get("pdf")
        out.append({
            "attempt": a.get("attempt"),
            "pdf": str(pdf) if pdf else "",
            "pages": a.get("pages"),
            "grade": a.get("grade"),
            "compile_error": a.get("compile_error"),
        })
    return out


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


def _first_bullet(profile: dict) -> str | None:
    for section in ("experience", "projects", "awards"):
        for entry in profile.get(section) or []:
            for b in entry.get("bullets") or []:
                if b:
                    return str(b)
    return None


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
