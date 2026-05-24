"""Pure helpers for filesystem persistence + profile-shaping during resume gen.

Extracted from ``generator.py`` so the orchestrator stays focused on the
attempt loop. None of these helpers touch network or AI providers.
"""
from __future__ import annotations

import logging
import pathlib
import re
import shutil
import uuid
from typing import Any

from ..app_settings import get_resume_output_dir
from .json_recovery import norm

logger = logging.getLogger(__name__)


# ---------- profile label helpers (canonical drop-label format) ----------

def exp_label(e: dict) -> str:
    role = (e.get("role") or "").strip()
    company = (e.get("company") or "").strip()
    if role and company:
        return f"{role} @ {company}"
    return role or company or "(unnamed experience)"


def project_label(p: dict) -> str:
    return (p.get("name") or "(unnamed project)").strip()


def award_label(a: dict) -> str:
    title = (a.get("title") or "").strip()
    issuer = (a.get("issuer") or "").strip()
    if title and issuer:
        return f"{title} — {issuer}"
    return title or issuer or "(unnamed award)"


def build_header_from_general_info(gi: dict) -> dict:
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


def apply_label_drops(profile: dict, omitted_labels: set[str]) -> dict:
    """Return a copy of profile with dropped entries and courses removed.

    Matches against entry labels (experience / project / award) and course
    strings (case-insensitive, whitespace-collapsed). Unmatched labels are
    logged and silently skipped.
    """
    out: dict[str, Any] = {k: v for k, v in profile.items()}
    if not omitted_labels:
        for k in ("experience", "projects", "awards", "education", "skills", "hobbies"):
            v = out.get(k)
            if isinstance(v, list):
                out[k] = list(v)
        return out

    matched: set[str] = set()

    def _keep_entry(label: str) -> bool:
        key = norm(label)
        if key in omitted_labels:
            matched.add(key)
            return False
        return True

    out["experience"] = [
        e for e in (profile.get("experience") or []) if _keep_entry(exp_label(e))
    ]
    out["projects"] = [
        p for p in (profile.get("projects") or []) if _keep_entry(project_label(p))
    ]
    out["awards"] = [
        a for a in (profile.get("awards") or []) if _keep_entry(award_label(a))
    ]

    new_education = []
    for edu in profile.get("education") or []:
        edu_copy = dict(edu)
        courses = edu_copy.get("courses") or []
        kept: list[str] = []
        for c in courses:
            key = norm(str(c))
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
            "apply_label_drops — %d label(s) had no match in profile: %s",
            len(unmatched), sorted(unmatched),
        )
    return out


def build_feedback(
    compile_error: str | None,
    fill: float | None,
    page_ok: bool,
    page_cap: int,
    last_drops: list[str],
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
            f"Entries/courses removed in the previous attempt: {'; '.join(last_drops)}."
            if last_drops
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


def attempts_summary(attempts: list[dict]) -> list[dict]:
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


def persist_pdf(
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
        logger.info("persist_pdf — PDF written to %s", target)
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
    logger.info("persist_pdf — PDF written to %s", target)
    return target, desired, collided
