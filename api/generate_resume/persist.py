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
from ..constants import RESUME_TARGET_FILL
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
    target_fill: float = RESUME_TARGET_FILL,
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
    elif (
        fill is not None
        and page_ok
        and target_fill is not None
        and fill < target_fill - 1e-6
    ):
        restore_note = (
            f" Consider restoring the most relevant of the previously-removed items: "
            f"{'; '.join(last_drops)}."
            if last_drops
            else ""
        )
        parts.append(
            f"UNDERFILLED: previous draft only filled {fill:.2f} of {page_cap} page(s); "
            f"aim closer to {target_fill:.2f}. You have room for more content —"
            f"{restore_note} Otherwise strengthen existing bullets with additional "
            "concrete detail/metric/keyword the profile already supports. Never invent facts."
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


def list_generated_resumes() -> list[tuple[pathlib.Path, str]]:
    """Saved resume PDFs in the output folder, newest first, with display labels."""
    out_dir = get_resume_output_dir()
    if not out_dir.exists():
        return []
    try:
        pdfs = sorted(out_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return []
    result = []
    for p in pdfs:
        stem = p.stem.removesuffix("_resume")  # older builds named files *_resume.pdf
        result.append((p, stem.replace("_", " ").replace("-", " ").strip().title() or p.name))
    return result


def tex_sidecar(pdf: pathlib.Path | str) -> pathlib.Path:
    """Return the ``.tex`` path that sits next to ``pdf``."""
    return pathlib.Path(pdf).with_suffix(".tex")


def write_tex_sidecar(pdf: pathlib.Path | str, latex: str) -> None:
    """Write ``latex`` to the sidecar next to ``pdf``."""
    path = tex_sidecar(pdf)
    path.write_text(latex, encoding="utf-8")
    logger.info("write_tex_sidecar — wrote %s", path)


def read_tex_sidecar(pdf: pathlib.Path | str) -> str | None:
    """Return sidecar LaTeX, or ``None`` if it is missing or unreadable."""
    path = tex_sidecar(pdf)
    try:
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8")
    except OSError:
        logger.exception("read_tex_sidecar — failed to read %s", path)
        return None


def remove_tex_sidecar(pdf: pathlib.Path | str) -> None:
    """Delete the sidecar next to ``pdf`` if it exists."""
    path = tex_sidecar(pdf)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.exception("remove_tex_sidecar — failed to remove %s", path)


def move_persisted_resume(src: pathlib.Path | str, dest: pathlib.Path | str) -> None:
    """Move a library PDF and its ``.tex`` sidecar, replacing ``dest``.

    If ``src`` has no sidecar, any existing dest sidecar is removed so the
    overwritten PDF is not paired with stale source.
    """
    src_pdf = pathlib.Path(src)
    dest_pdf = pathlib.Path(dest)
    dest_pdf.parent.mkdir(parents=True, exist_ok=True)
    if src_pdf.resolve() == dest_pdf.resolve():
        return

    src_tex = tex_sidecar(src_pdf)
    dest_tex = tex_sidecar(dest_pdf)
    shutil.move(str(src_pdf), str(dest_pdf))
    logger.info("move_persisted_resume — PDF %s → %s", src_pdf, dest_pdf)
    if src_tex.is_file():
        shutil.move(str(src_tex), str(dest_tex))
        logger.info("move_persisted_resume — tex %s → %s", src_tex, dest_tex)
    elif dest_tex.exists():
        dest_tex.unlink()
        logger.info("move_persisted_resume — removed stale dest sidecar %s", dest_tex)


def persist_pdf(
    src: pathlib.Path | None,
    dest: pathlib.Path | str | None,
    company: str | None = None,
    job_title: str | None = None,
    latex: str | None = None,
) -> tuple[pathlib.Path | None, pathlib.Path | None, bool]:
    """Copy ``src`` to the output location.

    Returns ``(written_path, desired_path, had_collision)``. When the
    preferred filename already exists, the file is written with a short
    UUID suffix and ``had_collision`` is True so the caller can prompt
    the user.

    When ``latex`` is non-empty, a ``.tex`` sidecar is written next to the
    **written** PDF (including UUID-suffixed collision names).
    """
    if src is None or not src.exists():
        return None, None, False
    if dest:
        target = pathlib.Path(dest)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        logger.info("persist_pdf — PDF written to %s", target)
        if latex:
            write_tex_sidecar(target, latex)
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
    if latex:
        write_tex_sidecar(target, latex)
    return target, desired, collided
