"""Deterministic LaTeX renderer for the drag-and-drop resume builder.

Produces a Jake-template document (same macros as
``prompts/resume_template.txt``) from a header dict plus an ordered list of
canvas sections. No LLM is involved.
"""
from __future__ import annotations

import logging
from pathlib import Path

from api.ai_provider import default_prompt

from .preview import compile_latex_preview

logger = logging.getLogger(__name__)

_BEGIN_DOC = r"\begin{document}"

# Placeholder so later `{` / `}` replacements don't mangle `\textbackslash{}`.
_BACKSLASH_TOKEN = "\x00BACKSLASH\x00"

_ESCAPE_TABLE = (
    ("&", r"\&"),
    ("%", r"\%"),
    ("$", r"\$"),
    ("#", r"\#"),
    ("_", r"\_"),
    ("{", r"\{"),
    ("}", r"\}"),
    ("~", r"\textasciitilde{}"),
    ("^", r"\textasciicircum{}"),
)

_LIST_KINDS = frozenset({"experience", "project", "education", "award", "hobbies"})


def escape_latex(text: str | None) -> str:
    """Escape characters that are special in LaTeX text mode."""
    if not text:
        return ""
    out = str(text).replace("\\", _BACKSLASH_TOKEN)
    for src, dst in _ESCAPE_TABLE:
        out = out.replace(src, dst)
    return out.replace(_BACKSLASH_TOKEN, r"\textbackslash{}")


def escape_url(url: str | None) -> str:
    """Escape a URL for use inside ``\\href{...}``."""
    if not url:
        return ""
    return (
        str(url)
        .replace("\\", "/")
        .replace("%", r"\%")
        .replace("#", r"\#")
        .replace("{", r"\{")
        .replace("}", r"\}")
    )


def render_manual_resume(header: dict, sections: list[dict]) -> str:
    """Build a full LaTeX document from *header* and ordered *sections*.

    ``header`` is the dict produced by
    :func:`api.generate_resume.persist.build_header_from_general_info`.

    Each section is ``{"title": str, "items": [{"kind": str, "data": dict}, ...]}``.
    Empty sections (no items) are omitted.
    """
    parts = [_load_preamble(), "", _BEGIN_DOC, "", _render_header(header or {}), ""]
    for section in sections or []:
        body = _render_section(section or {})
        if body:
            parts.append(body)
            parts.append("")
    parts.append(r"\end{document}")
    parts.append("")
    return "\n".join(parts)


def compile_manual_preview(latex: str) -> Path:
    """Compile builder LaTeX to a unique temp PDF (WebEngine cache-safe)."""
    pdf = compile_latex_preview(latex)
    logger.info("compile_manual_preview — compiled at %s", pdf)
    return pdf


# ---- preamble -----------------------------------------------------------

def _load_preamble() -> str:
    src = default_prompt("resume_template.txt")
    idx = src.find(_BEGIN_DOC)
    if idx < 0:
        raise ValueError("bundled resume template is missing \\begin{document}")
    return src[:idx].rstrip()


# ---- header -------------------------------------------------------------

def _render_header(header: dict) -> str:
    name = escape_latex((header.get("name") or "").strip() or "Your Name")
    bits: list[str] = []

    phone = (header.get("phone") or "").strip()
    if phone:
        bits.append(escape_latex(phone))

    email = (header.get("email") or "").strip()
    if email:
        bits.append(
            r"\href{mailto:" + escape_url(email) + r"}{\underline{"
            + escape_latex(email) + "}}"
        )

    location = (header.get("location") or "").strip()
    if location:
        bits.append(escape_latex(location))

    for link in header.get("links") or []:
        if not isinstance(link, dict):
            continue
        url = (link.get("url") or "").strip()
        if not url:
            continue
        href = _absolutize_url(url)
        display = _display_url(url)
        bits.append(
            r"\href{" + escape_url(href) + r"}{\underline{"
            + escape_latex(display) + "}}"
        )

    lines = [
        r"\begin{center}",
        r"    \textbf{\Huge \scshape " + name + r"} \\ \vspace{1pt}",
    ]
    if bits:
        joined = r" $|$ ".join(bits)
        lines.append(r"    \small " + joined)
    lines.append(r"\end{center}")
    return "\n".join(lines)


def _absolutize_url(url: str) -> str:
    lowered = url.lower()
    if lowered.startswith(("http://", "https://", "mailto:")):
        return url
    return "https://" + url


def _display_url(url: str) -> str:
    display = url.strip()
    for prefix in ("https://", "http://"):
        if display.lower().startswith(prefix):
            display = display[len(prefix):]
            break
    if display.startswith("www."):
        display = display[4:]
    return display.rstrip("/")


# ---- sections / items ---------------------------------------------------

def _render_section(section: dict) -> str:
    items = [it for it in (section.get("items") or []) if isinstance(it, dict)]
    if not items:
        return ""
    title = escape_latex((section.get("title") or "Section").strip() or "Section")
    chunks: list[str] = [r"\section{" + title + "}"]
    in_list = False

    def start_list() -> None:
        nonlocal in_list
        if not in_list:
            chunks.append(r"  \resumeSubHeadingListStart")
            in_list = True

    def end_list() -> None:
        nonlocal in_list
        if in_list:
            chunks.append(r"  \resumeSubHeadingListEnd")
            in_list = False

    for item in items:
        kind = (item.get("kind") or "").strip()
        data = item.get("data") or {}
        if not isinstance(data, dict):
            data = {}
        if kind in _LIST_KINDS:
            rendered = _render_list_item(kind, data)
            if rendered:
                start_list()
                chunks.append(rendered)
        else:
            end_list()
            rendered = _render_block_item(kind, data)
            if rendered:
                chunks.append(rendered)
    end_list()
    return "\n".join(chunks)


def _render_list_item(kind: str, data: dict) -> str:
    if kind == "experience":
        return _render_experience(data)
    if kind == "education":
        return _render_education(data)
    if kind == "project":
        return _render_project(data)
    if kind == "award":
        return _render_award(data)
    if kind == "hobbies":
        return _render_hobbies(data)
    return ""


def _render_block_item(kind: str, data: dict) -> str:
    if kind == "skills":
        return _render_skills(data)
    if kind == "text":
        return _render_text(data)
    return ""


def _render_experience(data: dict) -> str:
    title = escape_latex(data.get("title") or data.get("role") or "")
    company = escape_latex(data.get("company") or "")
    dates = escape_latex(_date_range(data.get("start"), data.get("end")))
    lines = [
        r"    \resumeSubheading",
        f"      {{{title}}}{{{dates}}}",
        f"      {{{company}}}{{}}",
    ]
    lines.extend(_bullet_block(data.get("bullets") or []))
    return "\n".join(lines)


def _render_education(data: dict) -> str:
    school = escape_latex(data.get("school") or "")
    dates = escape_latex(_date_range(data.get("start"), data.get("end")))
    line2 = _education_detail(data)
    lines = [
        r"    \resumeSubheading",
        f"      {{{school}}}{{}}",
        f"      {{{line2}}}{{{dates}}}",
    ]
    return "\n".join(lines)


def _education_detail(data: dict) -> str:
    degree = escape_latex(data.get("degree") or "")
    gpa = (data.get("gpa") or "").strip()
    courses = course_names(data)
    rows: list[str] = []
    if degree and gpa:
        rows.append(f"{degree} $|$ GPA: {escape_latex(gpa)}")
    elif degree:
        rows.append(degree)
    elif gpa:
        rows.append(f"GPA: {escape_latex(gpa)}")
    if courses:
        rows.append("Courses: " + ", ".join(escape_latex(c) for c in courses))
    if not rows:
        return ""
    if len(rows) == 1:
        return rows[0]
    return r"\parbox[t]{0.8\textwidth}{" + r"\\".join(rows) + "}"


def course_names(data: dict) -> list[str]:
    names: list[str] = []
    for course in data.get("courses") or []:
        if isinstance(course, dict):
            name = (course.get("name") or "").strip()
        else:
            name = str(course).strip()
        if name:
            names.append(name)
    return names


def _render_project(data: dict) -> str:
    name = escape_latex(data.get("name") or "")
    url = (data.get("url") or "").strip()
    if url and name:
        left = (
            r"\textbf{\href{" + escape_url(_absolutize_url(url))
            + r"}{\underline{" + name + "}}}"
        )
    else:
        left = r"\textbf{" + name + "}"
    dates = escape_latex(_date_range(data.get("start"), data.get("end")))
    lines = [
        r"    \resumeProjectHeading",
        f"      {{{left}}}{{{dates}}}",
    ]
    lines.extend(_bullet_block(data.get("bullets") or []))
    return "\n".join(lines)


def _render_award(data: dict) -> str:
    title = escape_latex(data.get("title") or "")
    issuer = escape_latex(data.get("issuer") or "")
    left = r"\textbf{" + title + "}"
    if issuer:
        left += r" $|$ \emph{" + issuer + "}"
    date = escape_latex((data.get("date") or "").strip())
    lines = [
        r"    \resumeProjectHeading",
        f"      {{{left}}}{{{date}}}",
    ]
    lines.extend(_bullet_block(data.get("bullets") or []))
    return "\n".join(lines)


def _render_hobbies(data: dict) -> str:
    items = _string_items(data)
    if not items:
        return ""
    label = escape_latex((data.get("label") or "Interests").strip() or "Interests")
    joined = escape_latex(", ".join(items))
    return (
        r"    \resumeProjectHeading"
        f"{{\\textbf{{{label}}} $|$ \\emph{{{joined}}}}}{{}}"
    )


def _render_skills(data: dict) -> str:
    items = _string_items(data)
    if not items:
        return ""
    bolded = ", ".join(r"\textbf{" + escape_latex(s) + "}" for s in items)
    label = escape_latex((data.get("label") or "Skills").strip() or "Skills")
    return (
        r" \begin{itemize}[leftmargin=0.15in, label={}]"
        "\n"
        r"    \small{\item{"
        "\n"
        f"     \\textbf{{{label}}}{{: {bolded}}}"
        "\n"
        r"    }}"
        "\n"
        r" \end{itemize}"
    )


def _render_text(data: dict) -> str:
    body = (data.get("body") or "").strip()
    if not body:
        return ""
    escaped = escape_latex(body).replace("\n", r" \\ ")
    return r" {\small " + escaped + "}"


def _bullet_block(bullets: list) -> list[str]:
    texts = [str(b).strip() for b in bullets if str(b).strip()]
    if not texts:
        return []
    lines = [r"      \resumeItemListStart"]
    for text in texts:
        lines.append(r"        \resumeItem{" + escape_latex(text) + "}")
    lines.append(r"      \resumeItemListEnd")
    return lines


def _date_range(start, end) -> str:
    a = (start or "").strip() if isinstance(start, str) else str(start or "").strip()
    b = (end or "").strip() if isinstance(end, str) else str(end or "").strip()
    if a and b:
        return f"{a} -- {b}"
    return a or b


def _string_items(data: dict) -> list[str]:
    raw = data.get("items")
    if raw is None:
        raw = data.get("skills") or data.get("hobbies") or []
    if isinstance(raw, str):
        raw = [p.strip() for p in raw.split(",")]
    return [str(s).strip() for s in raw if str(s).strip()]


__all__ = [
    "escape_latex",
    "escape_url",
    "render_manual_resume",
    "compile_manual_preview",
]
