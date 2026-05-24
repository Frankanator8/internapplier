from __future__ import annotations

import datetime
import json
import logging
import pathlib
from typing import Callable

from ..ai_provider import (
    TOOL_EVENT_PREFIX,
    OpenRouterProvider,
    get_max_generation_attempts,
    get_provider,
    get_resume_page_cap,
    get_resume_score_threshold,
)
from .agent_tools import detect_short_bullets
from .compile import LatexCompileError, compile_latex, pdf_page_metrics
from .json_recovery import (
    extract_json_object as _extract_json_object,
    norm as _norm,
    parse_lenient_json,
)
from .persist import (
    _build_pdf_filename,
    _clean_for_filename,
    apply_label_drops,
    apply_label_drops as _apply_label_drops,
    attempts_summary,
    build_feedback,
    build_feedback as _build_feedback,
    build_header_from_general_info,
    build_header_from_general_info as _build_header_from_general_info,
    persist_pdf,
    persist_pdf as _persist_pdf,
)
from .render import render_resume, validate_resume_shape
from .step_timing import time_call, time_step

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
        self._header = build_header_from_general_info(
            self.profile.get("general_info") or {}
        )

    # ---------- public API ----------

    @time_call("TOTAL")
    def generate_latex(
        self,
        output_pdf: pathlib.Path | str | None = None,
        company: str | None = None,
        job_title: str | None = None,
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
        score_threshold = get_resume_score_threshold()

        omitted_labels: set[str] = set()
        last_drops: list[str] = []
        feedback: str | None = None
        attempts: list[dict] = []

        from ..ai_provider import get_resume_template
        from ..ai_provider.keyword_extractor import extract_jd_keywords, format_jd_signals
        template = get_resume_template()

        with time_step("jd-keywords"):
            signals = extract_jd_keywords(self.job_description)
        _emit(
            stream_cb, "jd-keywords",
            "[jd-keywords] extracted from job description:\n" + format_jd_signals(signals),
        )

        for attempt in range(1, max_attempts + 1):
            logger.info("generate_latex — attempt %d/%d", attempt, max_attempts)
            profile_for_attempt = apply_label_drops(self.profile, omitted_labels)
            if progress_cb:
                progress_cb(f"Attempt {attempt}/{max_attempts}: generating resume JSON…")
            previous_resume = attempts[-1]["resume"] if attempts else None
            try:
                with time_step("generate-json", attempt):
                    resume_json = self._generate_resume_json(
                        profile_for_attempt, feedback, previous_resume, today, stream_cb
                    )
            except Exception:
                logger.exception("generate_latex — provider.generate_resume failed on attempt %d", attempt)
                raise

            try:
                resume_pretty = json.dumps(resume_json, indent=2)
            except Exception:
                resume_pretty = repr(resume_json)
            _emit(
                stream_cb, "generate-json",
                f"[generate-json] attempt {attempt} resume JSON:\n{resume_pretty}",
            )

            if progress_cb:
                progress_cb(f"Attempt {attempt}: rendering + compiling…")
            with time_step("render-compile", attempt):
                latex, pdf_path, compile_error = self._render_and_compile(
                    resume_json, template, attempt, stream_cb
                )
            if pdf_path is not None:
                metrics = pdf_page_metrics(pdf_path)
                fill = metrics["fill"]
                short_bullets = detect_short_bullets(
                    {**resume_json, "header": self._header},
                    metrics.get("lines") or [],
                )
            else:
                fill = None
                short_bullets = []

            page_ok = fill is not None and fill <= page_cap + 1e-6

            grade: dict | None = None
            if progress_cb:
                progress_cb(f"Attempt {attempt}: grading…")
            with time_step("grade", attempt):
                for grade_try in (1, 2):
                    try:
                        grade = self._grade_resume_text(
                            resume_json, fill, page_cap, today, profile_for_attempt, stream_cb
                        )
                        break
                    except ValueError:
                        logger.warning(
                            "generate_latex — grade parse failed on attempt %d (try %d/2)",
                            attempt, grade_try,
                        )
                        if grade_try == 2:
                            grade = None
                    except Exception:
                        logger.exception(
                            "generate_latex — grade_resume failed on attempt %d", attempt
                        )
                        grade = None
                        break
            if progress_cb and grade is not None:
                progress_cb(
                    f"Attempt {attempt}: graded {grade['score']:.2f}/10"
                )

            score_ok = grade is not None and grade["score"] >= score_threshold

            attempts.append({
                "resume": resume_json,
                "latex": latex,
                "pdf": pdf_path,
                "fill": fill,
                "grade": grade,
                "compile_error": compile_error,
                "attempt": attempt,
            })
            logger.info(
                "generate_latex — attempt %d: fill=%s score=%s compiled=%s short_bullets=%d",
                attempt,
                f"{fill:.3f}" if fill is not None else None,
                grade["score"] if grade else None,
                compile_error is None,
                len(short_bullets),
            )
            if short_bullets:
                logger.info(
                    "generate_latex — attempt %d short bullets: %s",
                    attempt,
                    "; ".join(
                        f"[{sb['lines']}L fill={sb['last_line_fill']:.2f}] {sb['text']}"
                        for sb in short_bullets
                    ),
                )

            if page_ok and score_ok:
                logger.info("generate_latex — passed on attempt %d", attempt)
                final_pdf, desired_pdf, collided = persist_pdf(
                    pdf_path, output_pdf, company, job_title
                )
                return {
                    "latex": latex,
                    "pdf": final_pdf,
                    "pdf_desired": desired_pdf,
                    "pdf_collision": collided,
                    "fill": fill,
                    "grade": grade,
                    "attempts": attempts_summary(attempts),
                    "chosen_attempt": attempt,
                }

            new_drops: list[str] = []
            if not page_ok and grade is not None:
                for d in grade.get("drops") or []:
                    if not isinstance(d, str):
                        continue
                    from .json_recovery import norm as _norm
                    key = _norm(d)
                    if key and key not in omitted_labels:
                        omitted_labels.add(key)
                        new_drops.append(d)
                if new_drops:
                    logger.info(
                        "generate_latex — page overflow (fill=%.3f > cap=%d), grader dropped: %s",
                        fill, page_cap, new_drops,
                    )
                last_drops = list(new_drops)

            feedback = build_feedback(
                compile_error, fill, page_ok, page_cap, last_drops, grade, score_ok,
                short_bullets,
            )

        best = self._pick_best_attempt(attempts, page_cap)
        logger.warning(
            "generate_latex — exhausted %d attempts; returning best (fill=%s, score=%s)",
            max_attempts,
            best.get("fill"),
            best["grade"]["score"] if best.get("grade") else None,
        )
        final_pdf, desired_pdf, collided = persist_pdf(
            best.get("pdf"), output_pdf, company, job_title
        )
        return {
            "latex": best["latex"],
            "pdf": final_pdf,
            "pdf_desired": desired_pdf,
            "pdf_collision": collided,
            "fill": best.get("fill"),
            "grade": best.get("grade"),
            "attempts": attempts_summary(attempts),
            "chosen_attempt": best.get("attempt"),
        }

    def _generate_resume_json(
        self,
        profile: dict,
        feedback: str | None,
        previous_resume: dict | None,
        today: str,
        stream_cb: Callable[[str, str], None] | None,
    ) -> dict:
        raw = _collect_stream(
            "generate",
            self.provider.generate_resume_stream(
                profile, self.job_description, feedback=feedback,
                previous_resume=previous_resume, today=today,
                company_research=self.company_research,
            ),
            stream_cb,
        )
        obj = parse_lenient_json(raw, log_label="_generate_resume_json")
        validate_resume_shape(obj)
        try:
            logger.info(
                "_generate_resume_json — resume JSON (%d chars):\n%s",
                len(raw), json.dumps(obj, indent=2),
            )
        except Exception:
            logger.info("_generate_resume_json — resume JSON keys=%s", list(obj.keys()))
        return obj

    def _render_and_compile(
        self,
        resume_json: dict,
        template: str,
        attempt: int,
        stream_cb: Callable[[str, str], None] | None,
    ) -> tuple[str, pathlib.Path | None, str | None]:
        resume_json = {**resume_json, "header": self._header}
        try:
            latex = render_resume(resume_json, template)
        except Exception as e:
            logger.exception("_render_and_compile — render failed")
            _emit(
                stream_cb, "render-error",
                f"[render-error] attempt {attempt}: {e}",
            )
            return "", None, f"render error: {e}"
        try:
            pdf_path = compile_latex(latex)
            return latex, pdf_path, None
        except LatexCompileError as e:
            err = f"{e}\n{e.log_excerpt}".strip()
            _emit(
                stream_cb, "compile-error",
                f"[compile-error] attempt {attempt}: LaTeX failed to compile "
                f"— grading anyway\n{err}",
            )
            return latex, None, err

    def _grade_resume_text(
        self,
        resume_json: dict,
        fill: float | None,
        page_cap: float,
        today: str,
        profile: dict,
        stream_cb: Callable[[str, str], None] | None,
    ) -> dict:
        raw = _collect_stream(
            "grade",
            self.provider.grade_resume_stream(
                resume_json, self.job_description,
                fill=fill, page_cap=page_cap, today=today,
                company_research=self.company_research,
                profile=profile,
            ),
            stream_cb,
        )
        obj = parse_lenient_json(raw, log_label="_grade_resume_text")

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
        if fill is not None and fill <= page_cap + 1e-6 and drops:
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
        logger.info(
            "_grade_resume_text — score=%.2f drops=%d; feedback:\n%s",
            score, len(drops), result["feedback"],
        )

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
