from __future__ import annotations

import datetime
import json
import logging
import pathlib
import re
import shutil
import uuid
from typing import Any, Callable

from api.ai_provider import (
    TOOL_EVENT_PREFIX,
    OpenRouterProvider,
    get_max_generation_attempts,
    get_provider,
    get_resume_output_dir,
    get_resume_page_cap,
    get_resume_score_threshold,
    strip_code_fence,
)

from .agent_tools import detect_short_bullets
from .compile import LatexCompileError, compile_latex, pdf_page_metrics
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


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


def _extract_json_object(text: str) -> str | None:
    """Return the first balanced ``{...}`` substring, or ``None`` if absent.

    Tolerates prose before/after the JSON. Respects string literals and
    backslash escapes so braces inside strings don't throw off the depth.
    """
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


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
        self._header = _build_header_from_general_info(
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
        all_drops_log: list[str] = []
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
            profile_for_attempt = _apply_label_drops(self.profile, omitted_labels)
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
            over_by = max(0.0, (fill or 0.0) - page_cap) if fill is not None else 0.0

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
                final_pdf, desired_pdf, collided = _persist_pdf(
                    pdf_path, output_pdf, company, job_title
                )
                return {
                    "latex": latex,
                    "pdf": final_pdf,
                    "pdf_desired": desired_pdf,
                    "pdf_collision": collided,
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
                compile_error, fill, page_ok, page_cap, all_drops_log, grade, score_ok,
                short_bullets,
            )

        best = self._pick_best_attempt(attempts, page_cap)
        logger.warning(
            "generate_latex — exhausted %d attempts; returning best (fill=%s, score=%s)",
            max_attempts,
            best.get("fill"),
            best["grade"]["score"] if best.get("grade") else None,
        )
        final_pdf, desired_pdf, collided = _persist_pdf(
            best.get("pdf"), output_pdf, company, job_title
        )
        return {
            "latex": best["latex"],
            "pdf": final_pdf,
            "pdf_desired": desired_pdf,
            "pdf_collision": collided,
            "fill": best.get("fill"),
            "grade": best.get("grade"),
            "attempts": _attempts_summary(attempts),
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
        raw = strip_code_fence(
            _collect_stream(
                "generate",
                self.provider.generate_resume_stream(
                    profile, self.job_description, feedback=feedback,
                    previous_resume=previous_resume, today=today,
                    company_research=self.company_research,
                ),
                stream_cb,
            ),
            lang_hints=("json",),
        )
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            extracted = _extract_json_object(raw)
            if extracted is None:
                logger.error("_generate_resume_json — JSON parse failed, raw=%r", raw[:500])
                raise ValueError("AI returned unexpected format — please try again.")
            obj = json.loads(extracted)
            logger.info(
                "_generate_resume_json — recovered JSON via balanced extract "
                "(%d chars of surrounding prose discarded)",
                len(raw) - len(extracted),
            )
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
        raw = strip_code_fence(
            _collect_stream(
                "grade",
                self.provider.grade_resume_stream(
                    resume_json, self.job_description,
                    fill=fill, page_cap=page_cap, today=today,
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
            extracted = _extract_json_object(raw)
            if extracted is None:
                logger.error("_grade_resume_text — JSON parse failed, raw=%r", raw[:500])
                raise ValueError("AI returned unexpected format — please try again.")
            try:
                obj = json.loads(extracted)
            except json.JSONDecodeError:
                logger.error(
                    "_grade_resume_text — balanced extract still unparseable, raw=%r",
                    raw[:500],
                )
                raise ValueError("AI returned unexpected format — please try again.")
            logger.info(
                "_grade_resume_text — recovered JSON via balanced extract "
                "(%d chars of surrounding prose discarded)",
                len(raw) - len(extracted),
            )
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
    short_bullets: list[dict] | None = None,
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
    if short_bullets:
        lines = [
            f"- ({sb['lines']} lines, last line fill={sb['last_line_fill']:.2f}) "
            f"{sb['text']}"
            for sb in short_bullets
        ]
        parts.append(
            "SHORT-TAIL BULLETS: the following bullets wrap with a mostly-empty "
            "final line — wasted vertical space. Either shorten each so it fits "
            "on one fewer line, or strengthen it with an additional concrete "
            "detail/metric/keyword that the profile already supports so the wrap "
            "is justified. Never invent facts.\n" + "\n".join(lines)
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


_FS_UNSAFE_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _clean_for_filename(s: str) -> str:
    s = _FS_UNSAFE_RE.sub("", s or "").strip().strip(".")
    s = re.sub(r"\s+", " ", s)
    return s


def _build_pdf_filename(company: str | None, job_title: str | None) -> str:
    c = _clean_for_filename(company or "")
    t = _clean_for_filename(job_title or "")[:15].strip()
    if c and t:
        return f"{c} - {t}.pdf"
    if c:
        return f"{c}.pdf"
    if t:
        return f"{t}.pdf"
    return "resume.pdf"


def _persist_pdf(
    src: pathlib.Path | None,
    dest: pathlib.Path | str | None,
    company: str | None = None,
    job_title: str | None = None,
) -> tuple[pathlib.Path | None, pathlib.Path | None, bool]:
    """Copy ``src`` to the output location.

    Returns ``(written_path, desired_path, had_collision)``. When the
    preferred filename already exists, the file is written with a short
    UUID suffix and ``had_collision`` is True so the caller can prompt
    the user.
    """
    if src is None or not src.exists():
        return None, None, False
    if dest:
        target = pathlib.Path(dest)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        logger.info("generate_latex — PDF written to %s", target)
        return target, target, False

    out_dir = get_resume_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    desired = out_dir / _build_pdf_filename(company, job_title)
    collided = desired.exists()
    if collided:
        suffix = uuid.uuid4().hex[:8]
        target = out_dir / f"{desired.stem}-{suffix}.pdf"
    else:
        target = desired
    shutil.copyfile(src, target)
    logger.info("generate_latex — PDF written to %s", target)
    return target, desired, collided


# ---------- label helpers (canonical drop-label format) ----------

def _exp_label(e: dict) -> str:
    role = (e.get("role") or "").strip()
    company = (e.get("company") or "").strip()
    if role and company:
        return f"{role} @ {company}"
    return role or company or "(unnamed experience)"


def _project_label(p: dict) -> str:
    return (p.get("name") or "(unnamed project)").strip()


def _build_header_from_general_info(gi: dict) -> dict:
    preferred = (gi.get("preferred_name") or "").strip()
    first = (gi.get("first_name") or "").strip()
    last = (gi.get("last_name") or "").strip()
    name = preferred or " ".join(p for p in (first, last) if p)

    location_parts = [
        (gi.get("city") or "").strip(),
        (gi.get("state") or "").strip(),
        (gi.get("country") or "").strip(),
    ]
    location = ", ".join(p for p in location_parts if p)

    links: list[dict] = []
    for label, key in (("LinkedIn", "linkedin"), ("GitHub", "github"), ("Website", "website")):
        url = (gi.get(key) or "").strip()
        if url:
            links.append({"label": label, "url": url})

    header: dict = {}
    if name:
        header["name"] = name
    for k in ("email", "phone"):
        v = (gi.get(k) or "").strip()
        if v:
            header[k] = v
    if location:
        header["location"] = location
    if links:
        header["links"] = links
    return header


def _award_label(a: dict) -> str:
    title = (a.get("title") or "").strip()
    issuer = (a.get("issuer") or "").strip()
    if title and issuer:
        return f"{title} — {issuer}"
    return title or issuer or "(unnamed award)"
