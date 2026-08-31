"""Parse an existing resume PDF into our resume schema.

Three steps, deliberately kept separate so the UI can report progress and so
each one is testable on its own:

    extract_text()        pypdf → plain text
    provider.extract_resume()  text → the model's JSON
    normalize_extraction()     that JSON → the profile-store shape

The last step is the trust boundary. Everything reaching it is model output
derived from a file the user supplied, so it is treated as untyped and
possibly hostile: values are coerced, unknown keys are dropped, and
``general_info`` is whitelisted against :data:`api.constants.LINE_FIELDS`.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from .constants import LINE_FIELDS

logger = logging.getLogger(__name__)

# Below this many characters we assume the PDF is a scan with no text layer.
MIN_TEXT_CHARS = 120
# Cap sent to the model. A 1-2 page resume is ~4-6k chars; this only bites on
# long academic CVs, and it keeps us clear of the provider's context limit.
MAX_TEXT_CHARS = 24_000

# Guards against a model that loses the plot and emits thousands of entries.
MAX_BULLETS_PER_ENTRY = 20
MAX_BULLET_CHARS = 600
MAX_FLAT_ITEMS = 150

_SECTION_KEYS = (
    "general_info", "experience", "projects", "education", "awards",
    "skills", "hobbies",
)

_BLANK_RUN_RE = re.compile(r"\n{3,}")


class ResumePdfError(Exception):
    """Import failure whose ``str()`` is safe to show the user verbatim."""


class NoTextInPdfError(ResumePdfError):
    """The PDF yielded (almost) no extractable text — a scan or image export."""


def extract_text(pdf_path: str | Path) -> str:
    """Return the plain text of a resume PDF, ready to hand to the model.

    Raises :class:`ResumePdfError` for anything the user can act on.
    """
    from pypdf import PdfReader

    try:
        reader = PdfReader(str(pdf_path))
    except Exception as exc:
        logger.exception("extract_text — could not open %s", pdf_path)
        raise ResumePdfError(
            f"Couldn't open that PDF — it may be corrupt or not a PDF at all.\n\n{exc}"
        ) from exc

    if reader.is_encrypted:
        try:
            opened = reader.decrypt("")
        except Exception:
            opened = 0
        if not opened:
            raise ResumePdfError(
                "This PDF is password-protected. Remove the password and try again."
            )

    pages: list[str] = []
    for page in reader.pages:
        try:
            # Layout mode preserves the whitespace between columns, which is
            # what lets the model read a two-column resume in the right order.
            text = page.extract_text(extraction_mode="layout")
        except Exception:
            # Older pypdf, or a page layout mode chokes on.
            try:
                text = page.extract_text()
            except Exception:
                logger.warning("extract_text — page extraction failed, skipping page")
                continue
        pages.append("\n".join(line.rstrip() for line in (text or "").splitlines()))

    combined = _BLANK_RUN_RE.sub("\n\n", "\n\n".join(pages)).strip()

    if len(combined) < MIN_TEXT_CHARS:
        raise NoTextInPdfError(
            "This PDF has no selectable text — it looks like a scan or an image "
            "export, and the app doesn't do OCR.\n\n"
            "Export a text-based PDF from Word, Google Docs, or LaTeX and try again."
        )

    if len(combined) > MAX_TEXT_CHARS:
        cut = combined.rfind("\n", 0, MAX_TEXT_CHARS)
        if cut < MAX_TEXT_CHARS // 2:
            cut = MAX_TEXT_CHARS
        logger.warning(
            "extract_text — %d chars truncated to %d", len(combined), cut
        )
        combined = combined[:cut].rstrip() + "\n\n[…truncated]"

    return combined


def parse_text(text: str, *, provider=None) -> dict:
    """Send resume text to the model and return it in the profile-store shape."""
    if provider is None:
        from .ai_provider import get_provider
        provider = get_provider()
    return normalize_extraction(provider.extract_resume(text))


def parse_pdf(pdf_path: str | Path, *, provider=None) -> dict:
    """Convenience wrapper: :func:`extract_text` then :func:`parse_text`."""
    return parse_text(extract_text(pdf_path), provider=provider)


# ── Normalization ───────────────────────────────────────────────────────────

def _s(value) -> str:
    """Coerce a model-supplied scalar to a stripped string."""
    if value is None or isinstance(value, bool):
        return ""
    return str(value).strip()


def _str_list(value, *, limit: int = MAX_FLAT_ITEMS) -> list[str]:
    if not isinstance(value, list):
        return []
    out = [_s(x) for x in value]
    return [x for x in out if x][:limit]


def _bullets(value) -> list[str]:
    return [b[:MAX_BULLET_CHARS] for b in _str_list(value, limit=MAX_BULLETS_PER_ENTRY)]


def _dedupe_ci(items: list[str]) -> list[str]:
    """Dedupe case-insensitively, keeping first-occurrence order."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _entries(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [e for e in value if isinstance(e, dict)]


def _courses(value) -> list[dict]:
    out = []
    for course in _entries(value):
        name = _s(course.get("name"))
        if not name:
            continue
        # CoursesWidget expects a skills key even though a resume never
        # prints skills per course.
        out.append({"name": name, "grade": _s(course.get("grade")), "skills": []})
    return out


def normalize_extraction(raw: dict) -> dict:
    """Coerce raw model output into the profile-store shape.

    Always returns every section key. Entries missing their identifying field
    are dropped rather than added as blank cards.
    """
    if not isinstance(raw, dict):
        raw = {}

    gi_in = raw.get("general_info")
    gi_in = gi_in if isinstance(gi_in, dict) else {}
    # Whitelist, not blacklist. COMBO_FIELDS are constrained enums that
    # GeneralInfoPage.load() silently discards on a near-miss, and they cover
    # work authorization and EEO answers — never AI-guessable. The schema
    # already omits them, but the schema is a user-editable prompt file, so
    # this filter is the actual guard.
    general_info = {}
    for key in LINE_FIELDS:
        value = _s(gi_in.get(key))
        if value:
            general_info[key] = value

    experience = []
    for entry in _entries(raw.get("experience")):
        company = _s(entry.get("company"))
        title = _s(entry.get("title"))
        if not company and not title:
            continue
        category = _s(entry.get("category")).lower()
        experience.append({
            "company": company,
            "title": title,
            "start": _s(entry.get("start")),
            "end": _s(entry.get("end")),
            "bullets": _bullets(entry.get("bullets")),
            "skills": _str_list(entry.get("skills")),
            "category": category if category in ("relevant", "other") else "relevant",
        })

    projects = []
    for entry in _entries(raw.get("projects")):
        name = _s(entry.get("name"))
        if not name:
            continue
        projects.append({
            "name": name,
            "url": _s(entry.get("url")),
            "start": _s(entry.get("start")),
            "end": _s(entry.get("end")),
            "bullets": _bullets(entry.get("bullets")),
            "skills": _str_list(entry.get("skills")),
        })

    education = []
    for entry in _entries(raw.get("education")):
        school = _s(entry.get("school"))
        if not school:
            continue
        education.append({
            "school": school,
            "degree": _s(entry.get("degree")),
            "start": _s(entry.get("start")),
            "end": _s(entry.get("end")),
            "gpa": _s(entry.get("gpa")),
            "courses": _courses(entry.get("courses")),
        })

    awards = []
    for entry in _entries(raw.get("awards")):
        title = _s(entry.get("title"))
        if not title:
            continue
        awards.append({
            "title": title,
            "issuer": _s(entry.get("issuer")),
            "date": _s(entry.get("date")),
            "bullets": _bullets(entry.get("bullets")),
            "skills": _str_list(entry.get("skills")),
        })

    return {
        "general_info": general_info,
        "experience": experience,
        "projects": projects,
        "education": education,
        "awards": awards,
        "skills": _dedupe_ci(_str_list(raw.get("skills"))),
        "hobbies": _dedupe_ci(_str_list(raw.get("hobbies"))),
    }


# ── Reporting / applying ────────────────────────────────────────────────────

def summarize(data: dict) -> str:
    """Short human summary of an imported dict — used in status messages."""
    parts = [
        f"{len(data.get('experience') or [])} experience",
        f"{len(data.get('projects') or [])} projects",
        f"{len(data.get('education') or [])} education",
        f"{len(data.get('awards') or [])} awards",
        f"{len(data.get('skills') or [])} skills",
    ]
    if data.get("hobbies"):
        parts.append(f"{len(data['hobbies'])} hobbies")
    summary = " · ".join(parts)
    if data.get("general_info"):
        summary += " + identity"
    return summary


def is_empty(data: dict) -> bool:
    """True when there is nothing worth showing the user."""
    return not any(data.get(k) for k in _SECTION_KEYS)


def apply_to_store(data: dict, mode: str = "append") -> None:
    """Merge an imported dict into the on-disk resume store.

    Used by flows without a main window (onboarding). The toolbar path in
    MainWindow updates live UI widgets instead.
    """
    from .profile_merge import apply_to_store as _apply

    _apply(data, mode)
