"""Render a structured resume (JSON) into LaTeX via a Jinja-style template.

Custom Jinja delimiters are used so they don't collide with LaTeX braces:

    statements: ((*  ... *))
    expressions: ((( ... )))
    comments:   ((=  ... =))

A `latex_escape` filter is exposed (aliased `e`) and applied to every
user-supplied string in the default template.
"""
from __future__ import annotations

import logging

from jinja2 import ChainableUndefined, Environment, TemplateSyntaxError

logger = logging.getLogger(__name__)


_ESCAPE_MAP = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

_SMART_REPLACE = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": "``", "”": "''", "„": ",,",
    "–": "--", "—": "---",
    "…": "...",
    " ": " ",
}


def latex_escape(value) -> str:
    if value is None:
        return ""
    s = str(value)
    for src, dst in _SMART_REPLACE.items():
        if src in s:
            s = s.replace(src, dst)
    # Order matters: backslash must be replaced first to avoid double-escaping.
    s = s.replace("\\", _ESCAPE_MAP["\\"])
    for ch, repl in _ESCAPE_MAP.items():
        if ch == "\\":
            continue
        s = s.replace(ch, repl)
    return s


def _date_range(start, end) -> str:
    s = str(start or "").strip()
    e = str(end or "").strip()
    if s and e:
        return f"{s} -- {e}"
    return s or e


DEFAULT_TEMPLATE = r"""\documentclass[11pt]{article}
\usepackage[margin=0.75in]{geometry}
\usepackage{hyperref}
\usepackage{enumitem}
\usepackage{titlesec}
\setlist[itemize]{leftmargin=*,topsep=2pt,itemsep=1pt,parsep=0pt}
\titleformat{\section}{\large\bfseries}{}{0pt}{}[\titlerule]
\titlespacing*{\section}{0pt}{6pt}{4pt}
\pagestyle{empty}

\begin{document}

((* if header.name or header.email or header.phone or header.location or header.links *))
\begin{center}
((* if header.name *)){\LARGE\bfseries (((header.name | e)))}\\[2pt]((* endif *))
((* set contact = [] *))
((* if header.email *))((* set _ = contact.append(header.email | e) *))((* endif *))
((* if header.phone *))((* set _ = contact.append(header.phone | e) *))((* endif *))
((* if header.location *))((* set _ = contact.append(header.location | e) *))((* endif *))
((* for link in header.links or [] *))
((* set _ = contact.append('\\href{' ~ link.url ~ '}{' ~ (link.label | e) ~ '}') *))
((* endfor *))
(((contact | join(' \\textbar{} '))))
\end{center}
((* endif *))

((* for section in sections *))
((* if section.kind == 'experience' *))
\section*{((( section.title | default('Experience') | e )))}
((* for it in section['items'] or [] *))
\noindent\textbf{((( it.role | e ))) \textbar{} ((( it.company | e )))}\hfill{\itshape ((( date_range(it.start, it.end) | e )))}\\
((* if it.location *)){\itshape ((( it.location | e )))}\\((* endif *))
((* if it.bullets *))
\begin{itemize}
((* for b in it.bullets *))
  \item ((( b | e )))
((* endfor *))
\end{itemize}
((* endif *))
((* endfor *))

((* elif section.kind == 'projects' *))
\section*{((( section.title | default('Projects') | e )))}
((* for it in section['items'] or [] *))
\noindent\textbf{((( it.name | e )))}((* if it.tagline *)) -- {\itshape ((( it.tagline | e )))}((* endif *))\hfill{\itshape ((( date_range(it.start, it.end) | e )))}\\
((* if it.bullets *))
\begin{itemize}
((* for b in it.bullets *))
  \item ((( b | e )))
((* endfor *))
\end{itemize}
((* endif *))
((* endfor *))

((* elif section.kind == 'education' *))
\section*{((( section.title | default('Education') | e )))}
((* for it in section['items'] or [] *))
\noindent\textbf{((( it.school | e )))}((* if it.degree *)), ((( it.degree | e )))((* endif *))\hfill{\itshape ((( date_range(it.start, it.end) | e )))}\\
((* if it.gpa *)){\itshape GPA: ((( it.gpa | e )))}\\((* endif *))
((* if it.courses *))
\textbf{Courses:} ((( it.courses | map('e') | join(', ') )))\\
((* endif *))
((* endfor *))

((* elif section.kind == 'skills' *))
\section*{((( section.title | default('Skills') | e )))}
((* for g in section.groups or [] *))
\noindent\textbf{((( g.label | e ))):} ((( (g['items'] or []) | map('e') | join(', ') )))\\
((* endfor *))

((* elif section.kind == 'awards' *))
\section*{((( section.title | default('Awards') | e )))}
\begin{itemize}
((* for it in section['items'] or [] *))
  \item \textbf{((( it.title | e )))} -- ((( it.issuer | e )))((* if it.date *)) \hfill {\itshape ((( it.date | e )))}((* endif *))
((* endfor *))
\end{itemize}

((* elif section.kind == 'hobbies' *))
\section*{((( section.title | default('Hobbies') | e )))}
((( (section['items'] or []) | map('e') | join(', ') )))
((* endif *))
((* endfor *))

\end{document}
"""


def _make_env() -> Environment:
    env = Environment(
        block_start_string="((*",
        block_end_string="*))",
        variable_start_string="(((",
        variable_end_string=")))",
        comment_start_string="((=",
        comment_end_string="=))",
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
        undefined=ChainableUndefined,
    )
    env.filters["e"] = latex_escape
    env.filters["latex_escape"] = latex_escape
    env.globals["date_range"] = _date_range
    return env


_env = _make_env()


def _is_jinja_template(s: str) -> bool:
    return bool(s) and ("(((" in s or "((*" in s)


def pick_template(user_template: str | None) -> str:
    """Return a usable Jinja template. Falls back to the bundled default
    when the user has no template or has the legacy raw-LaTeX format."""
    if user_template and _is_jinja_template(user_template):
        return user_template
    if user_template:
        logger.info(
            "render — user template lacks Jinja markers; falling back to default template"
        )
    return DEFAULT_TEMPLATE


def render_resume(resume: dict, template: str | None = None) -> str:
    """Render `resume` (validated JSON-shaped dict) to LaTeX source."""
    tmpl_src = pick_template(template)
    try:
        tmpl = _env.from_string(tmpl_src)
    except TemplateSyntaxError as e:
        if tmpl_src is DEFAULT_TEMPLATE:
            raise
        logger.warning(
            "render — user template has Jinja syntax error (%s); falling back to default template",
            e,
        )
        tmpl = _env.from_string(DEFAULT_TEMPLATE)
    return tmpl.render(
        header=resume.get("header") or {},
        sections=resume.get("sections") or [],
    )


def validate_resume_shape(resume) -> None:
    """Cheap structural validation — raise ValueError with a useful
    message so the orchestrator can feed it back to the model."""
    if not isinstance(resume, dict):
        raise ValueError("resume JSON must be an object")
    sections = resume.get("sections")
    if not isinstance(sections, list):
        raise ValueError("resume.sections must be an array")
    for i, sec in enumerate(sections):
        if not isinstance(sec, dict):
            raise ValueError(f"resume.sections[{i}] must be an object")
        if not sec.get("kind"):
            raise ValueError(f"resume.sections[{i}].kind is required")
