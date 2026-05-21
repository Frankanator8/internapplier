from __future__ import annotations

import datetime
import json
import logging
import pathlib
import re
import shutil
from typing import Any, Callable

from api.ai_provider import (
    TOOL_EVENT_PREFIX,
    OpenRouterProvider,
    get_max_generation_attempts,
    get_provider,
    get_resume_output_dir,
    get_resume_page_cap,
)

from .compile import LatexCompileError, compile_latex, extract_document, pdf_page_fill

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
        if chunk.startswith(TOOL_EVENT_PREFIX):
            event_text = chunk[len(TOOL_EVENT_PREFIX):]
            if stream_cb is not None:
                stream_cb(f"{stage}-tool", event_text)
            continue
        parts.append(chunk)
        if stream_cb is not None:
            stream_cb(stage, chunk)
    return "".join(parts).strip()


def _strip_code_fence(raw: str, lang_hints: tuple[str, ...] = ()) -> str:
    raw = raw.strip()
    for hint in lang_hints:
        closed = re.search(
            r"```" + re.escape(hint) + r"[ \t]*\r?\n(.*?)```",
            raw, re.DOTALL | re.IGNORECASE,
        )
        if closed:
            return closed.group(1).strip()
        unclosed = re.search(
            r"```" + re.escape(hint) + r"[ \t]*\r?\n(.*)\Z",
            raw, re.DOTALL | re.IGNORECASE,
        )
        if unclosed:
            return unclosed.group(1).rstrip("`").strip()
    closed = re.search(r"```[a-zA-Z0-9_+-]*[ \t]*\r?\n(.*?)```", raw, re.DOTALL)
    if closed:
        return closed.group(1).strip()
    unclosed = re.search(r"```[a-zA-Z0-9_+-]*[ \t]*\r?\n(.*)\Z", raw, re.DOTALL)
    if unclosed:
        return unclosed.group(1).rstrip("`").strip()
    return raw


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


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
        self.provider: OpenRouterProvider = provider or get_provider("powerful")

    # ---------- public API ----------

    def generate_latex(
        self,
        output_pdf: pathlib.Path | str | None = None,
        company: str | None = None,
        progress_cb: Callable[[str], None] | None = None,
        stream_cb: Callable[[str, str], None] | None = None,
    ) -> dict:
        """Generate, compile, and grade the resume.

        The AI receives the full profile and decides what to include. When
        the rendered draft exceeds the page cap, the grader returns a
        `drops` array of entry labels and/or course names; the orchestrator
        removes those from the profile and regenerates.
        """
        today = datetime.date.today().isoformat()
        page_cap = get_resume_page_cap()
        max_attempts = get_max_generation_attempts()

        omitted_labels: set[str] = set()
        all_drops_log: list[str] = []
        feedback: str | None = None
        attempts: list[dict] = []

        for attempt in range(1, max_attempts + 1):
            logger.info("generate_latex — attempt %d/%d", attempt, max_attempts)
            profile_for_attempt = _apply_label_drops(self.profile, omitted_labels)
            if progress_cb:
                progress_cb(f"Attempt {attempt}/{max_attempts}: generating LaTeX…")
            previous_latex = attempts[-1]["latex"] if attempts else None
            try:
                latex = self._generate_resume_text(
                    profile_for_attempt, feedback, previous_latex, today, stream_cb
                )
            except Exception:
                logger.exception("generate_latex — provider.generate_resume failed on attempt %d", attempt)
                raise

            if progress_cb:
                progress_cb(f"Attempt {attempt}: compiling LaTeX…")
            latex, pdf_path, compile_error = self._compile_with_fix(
                latex, attempt, progress_cb, stream_cb
            )
            fill = pdf_page_fill(pdf_path) if pdf_path is not None else None

            page_ok = fill is not None and fill <= page_cap + 1e-6
            over_by = max(0.0, (fill or 0.0) - page_cap) if fill is not None else 0.0

            grade: dict | None = None
            if progress_cb:
                progress_cb(f"Attempt {attempt}: grading…")
            try:
                grade = self._grade_resume_text(
                    latex, over_by, today, profile_for_attempt, stream_cb
                )
            except Exception:
                logger.exception("generate_latex — grade_resume failed on attempt %d", attempt)
                grade = None
            if progress_cb and grade is not None:
                progress_cb(
                    f"Attempt {attempt}: graded {grade['score']:.2f}/10"
                )

            score_ok = grade is not None and grade["score"] >= SCORE_THRESHOLD

            attempts.append({
                "latex": latex,
                "pdf": pdf_path,
                "fill": fill,
                "grade": grade,
                "compile_error": compile_error,
                "attempt": attempt,
            })
            logger.info(
                "generate_latex — attempt %d: fill=%s score=%s compiled=%s",
                attempt,
                f"{fill:.3f}" if fill is not None else None,
                grade["score"] if grade else None,
                compile_error is None,
            )

            if page_ok and score_ok:
                logger.info("generate_latex — passed on attempt %d", attempt)
                final_pdf = _persist_pdf(pdf_path, output_pdf, company)
                return {
                    "latex": latex,
                    "pdf": final_pdf,
                    "fill": fill,
                    "grade": grade,
                    "attempts": _attempts_summary(attempts),
                    "chosen_attempt": attempt,
                }

            new_drops: list[str] = []
            if not page_ok and grade is not None:
                for d in grade.get("drops") or []:
                    if not isinstance(d, str):
                        continue
                    key = _norm(d)
                    if key and key not in omitted_labels:
                        omitted_labels.add(key)
                        new_drops.append(d)
                if new_drops:
                    all_drops_log.extend(new_drops)
                    logger.info(
                        "generate_latex — page overflow (fill=%.3f > cap=%d), grader dropped: %s",
                        fill, page_cap, new_drops,
                    )

            feedback = _build_feedback(
                compile_error, fill, page_ok, page_cap, all_drops_log, grade, score_ok
            )

        best = self._pick_best_attempt(attempts, page_cap)
        logger.warning(
            "generate_latex — exhausted %d attempts; returning best (fill=%s, score=%s)",
            max_attempts,
            best.get("fill"),
            best["grade"]["score"] if best.get("grade") else None,
        )
        final_pdf = _persist_pdf(best.get("pdf"), output_pdf, company)
        return {
            "latex": best["latex"],
            "pdf": final_pdf,
            "fill": best.get("fill"),
            "grade": best.get("grade"),
            "attempts": _attempts_summary(attempts),
            "chosen_attempt": best.get("attempt"),
        }

    def _generate_resume_text(
        self,
        profile: dict,
        feedback: str | None,
        previous_latex: str | None,
        today: str,
        stream_cb: Callable[[str, str], None] | None,
    ) -> str:
        raw = _strip_code_fence(
            _collect_stream(
                "generate",
                self.provider.generate_resume_stream(
                    profile, self.job_description, feedback=feedback,
                    previous_latex=previous_latex, today=today,
                    company_research=self.company_research,
                ),
                stream_cb,
            ),
            lang_hints=("latex", "tex"),
        )
        extracted = extract_document(raw)
        if extracted is None:
            logger.warning(
                "_generate_resume_text — output missing \\documentclass{...} "
                "(%d chars); passing raw output to compiler",
                len(raw),
            )
            return raw
        if extracted != raw:
            logger.info(
                "_generate_resume_text — trimmed %d chars of surrounding prose",
                len(raw) - len(extracted),
            )
        return extracted

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
        _emit(
            stream_cb,
            "compile-error",
            f"[compile-error] attempt {attempt}: LaTeX failed to compile "
            f"— grading raw LaTeX anyway\n{compile_error}",
        )
        if progress_cb:
            progress_cb(f"Attempt {attempt}: compile failed — grading anyway")
        return latex, None, compile_error

    def _grade_resume_text(
        self,
        latex: str,
        over_by: float,
        today: str,
        profile: dict,
        stream_cb: Callable[[str, str], None] | None,
    ) -> dict:
        raw = _strip_code_fence(
            _collect_stream(
                "grade",
                self.provider.grade_resume_stream(
                    latex, self.job_description,
                    over_by=over_by, today=today,
                    company_research=self.company_research,
                    profile=profile,
                ),
                stream_cb,
            ),
            lang_hints=("json",),
        )
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("_grade_resume_text — JSON parse failed, raw=%r", raw[:500])
            raise ValueError("AI returned unexpected format — please try again.")
        required = ("score", "feedback")
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

        drops_raw = obj.get("drops") or []
        drops: list[str] = [str(d) for d in drops_raw if isinstance(d, str) and d.strip()]
        if over_by <= 1e-6 and drops:
            logger.info(
                "_grade_resume_text — discarding %d drop(s) since page count is fine: %s",
                len(drops), drops,
            )
            drops = []

        result = {
            "score": score,
            "feedback": str(obj["feedback"]),
            "drops": drops,
        }

        def _indent(text: str, prefix: str = "    ") -> str:
            return "\n".join(prefix + ln for ln in (text or "").splitlines()) or (prefix + "(empty)")

        lines = [f"[grader] score={score:.2f}/10"]
        if drops:
            lines.append("  drops: " + "; ".join(drops))
        lines.extend(["  feedback:", _indent(result["feedback"])])
        _emit(stream_cb, "grade-result", "\n".join(lines))

        return result

    @staticmethod
    def _pick_best_attempt(attempts: list[dict], page_cap: int) -> dict:
        def key(a: dict) -> tuple:
            compiled = a.get("compile_error") is None
            page_ok = a.get("fill") is not None and a["fill"] <= page_cap + 1e-6
            score = a["grade"]["score"] if a.get("grade") else -1.0
            return (compiled, page_ok, score)

        return max(attempts, key=key)


def _apply_label_drops(profile: dict, omitted_labels: set[str]) -> dict:
    """Return a copy of profile with dropped entries and courses removed.

    Matches against entry labels (experience / project / award) and course
    strings (case-insensitive, whitespace-collapsed). Unmatched labels are
    logged and silently skipped.
    """
    out: dict[str, Any] = {k: v for k, v in profile.items()}
    if not omitted_labels:
        # still return shallow copies of lists to avoid aliasing
        for k in ("experience", "projects", "awards", "education", "skills", "hobbies"):
            v = out.get(k)
            if isinstance(v, list):
                out[k] = list(v)
        return out

    matched: set[str] = set()

    def _keep_entry(label: str) -> bool:
        key = _norm(label)
        if key in omitted_labels:
            matched.add(key)
            return False
        return True

    out["experience"] = [
        e for e in (profile.get("experience") or []) if _keep_entry(_exp_label(e))
    ]
    out["projects"] = [
        p for p in (profile.get("projects") or []) if _keep_entry(_project_label(p))
    ]
    out["awards"] = [
        a for a in (profile.get("awards") or []) if _keep_entry(_award_label(a))
    ]

    new_education = []
    for edu in profile.get("education") or []:
        edu_copy = dict(edu)
        courses = edu_copy.get("courses") or []
        kept: list[str] = []
        for c in courses:
            key = _norm(str(c))
            if key in omitted_labels:
                matched.add(key)
                continue
            kept.append(c)
        edu_copy["courses"] = kept
        new_education.append(edu_copy)
    out["education"] = new_education

    out["skills"] = list(profile.get("skills") or [])
    out["hobbies"] = list(profile.get("hobbies") or [])

    unmatched = omitted_labels - matched
    if unmatched:
        logger.info(
            "_apply_label_drops — %d label(s) had no match in profile: %s",
            len(unmatched), sorted(unmatched),
        )
    return out


def _build_feedback(
    compile_error: str | None,
    fill: float | None,
    page_ok: bool,
    page_cap: int,
    all_drops: list[str],
    grade: dict | None,
    score_ok: bool,
) -> str | None:
    parts: list[str] = []
    if compile_error:
        parts.append(
            "PREVIOUS DRAFT FAILED TO COMPILE. Fix the LaTeX syntax. "
            f"Compiler output:\n{compile_error}"
        )
    if fill is not None and not page_ok:
        drop_note = (
            f"Entries/courses removed so far across attempts: {'; '.join(all_drops)}."
            if all_drops
            else "The grader did not name anything to drop — tighten remaining content."
        )
        parts.append(
            f"PAGE OVERFLOW: previous draft filled {fill:.2f} pages; the resume MUST fit on "
            f"{page_cap}. {drop_note} Do NOT include any removed items. Tighten "
            "margins/spacing if possible and shorten remaining bullets where you can. "
            "Length may drop below the original — but keep the most important "
            "information (lead action verb, primary impact metric, key tools relevant "
            "to the JD); drop secondary clauses first. Never invent facts."
        )
    if grade is not None and not score_ok and grade.get("feedback"):
        parts.append("GRADER FEEDBACK:\n" + grade["feedback"])
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
            "fill": a.get("fill"),
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


# ---------- label helpers (canonical drop-label format) ----------

def _exp_label(e: dict) -> str:
    role = (e.get("role") or "").strip()
    company = (e.get("company") or "").strip()
    if role and company:
        return f"{role} @ {company}"
    return role or company or "(unnamed experience)"


def _project_label(p: dict) -> str:
    return (p.get("name") or "(unnamed project)").strip()


def _award_label(a: dict) -> str:
    title = (a.get("title") or "").strip()
    issuer = (a.get("issuer") or "").strip()
    if title and issuer:
        return f"{title} — {issuer}"
    return title or issuer or "(unnamed award)"
