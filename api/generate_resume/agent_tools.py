from __future__ import annotations

import logging
from typing import Any, Callable

from .compile import (
    LatexCompileError,
    compile_latex,
    pdf_page_fill,
    test_latex_compiles,
)

logger = logging.getLogger(__name__)

_MAX_LOG_EXCERPT = 1500

_MINIMAL_PREAMBLE = r"""\documentclass[11pt]{article}
\usepackage[margin=0.75in]{geometry}
\usepackage{hyperref}
\usepackage{enumitem}
\usepackage{titlesec}
\begin{document}
"""
_MINIMAL_POSTAMBLE = "\n\\end{document}\n"


def extract_preamble(latex: str) -> str | None:
    """Return everything from ``\\documentclass`` up to and including
    ``\\begin{document}\\n`` from ``latex``, or ``None`` if no preamble can
    be parsed. Used so snippet tests inherit the real document's packages
    and macros rather than a fixed minimal preamble that lies about
    template-specific failures.
    """
    if not isinstance(latex, str):
        return None
    doc_idx = latex.find("\\documentclass")
    if doc_idx < 0:
        return None
    begin_idx = latex.find("\\begin{document}", doc_idx)
    if begin_idx < 0:
        return None
    end_of_begin = latex.find("\n", begin_idx)
    if end_of_begin < 0:
        end_of_begin = begin_idx + len("\\begin{document}")
    return latex[doc_idx:end_of_begin] + "\n"


def _wrap_if_snippet(latex: str, preamble: str | None = None) -> str:
    if "\\documentclass" in latex:
        return latex
    return (preamble or _MINIMAL_PREAMBLE) + latex + _MINIMAL_POSTAMBLE


def make_test_compile(preamble: str | None) -> Callable[..., dict[str, Any]]:
    """Build a ``test_compile`` handler that wraps snippets in ``preamble``
    instead of the fixed minimal preamble. Pass ``None`` to fall back to
    the minimal preamble."""

    def _test_compile(latex: str) -> dict[str, Any]:
        if not isinstance(latex, str) or not latex.strip():
            return {"ok": False, "log_excerpt": "empty latex argument"}
        document = _wrap_if_snippet(latex, preamble)
        ok, excerpt = test_latex_compiles(document)
        return {"ok": ok, "log_excerpt": _truncate(excerpt)}

    return _test_compile


def _truncate(text: str, limit: int = _MAX_LOG_EXCERPT) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n…[truncated {len(text) - limit} chars]"


def test_compile(latex: str) -> dict[str, Any]:
    """Compile `latex` (full doc or snippet) and report success."""
    if not isinstance(latex, str) or not latex.strip():
        return {"ok": False, "log_excerpt": "empty latex argument"}
    document = _wrap_if_snippet(latex)
    ok, excerpt = test_latex_compiles(document)
    return {"ok": ok, "log_excerpt": _truncate(excerpt)}


def page_length(latex: str) -> dict[str, Any]:
    """Compile `latex` and return its pdf_page_fill alongside the configured page cap."""
    # Imported lazily to avoid a circular import (ai_provider <-> agent_tools).
    from api.ai_provider import get_resume_page_cap

    page_cap = get_resume_page_cap()
    if not isinstance(latex, str) or not latex.strip():
        return {"ok": False, "page_cap": page_cap, "log_excerpt": "empty latex argument"}
    document = _wrap_if_snippet(latex)
    try:
        pdf_path = compile_latex(document)
    except LatexCompileError as e:
        excerpt = getattr(e, "log_excerpt", "") or str(e)
        return {"ok": False, "page_cap": page_cap, "log_excerpt": _truncate(excerpt)}
    try:
        fill = pdf_page_fill(pdf_path)
    except Exception as e:
        logger.exception("page_length — pdf_page_fill failed")
        return {"ok": False, "page_cap": page_cap, "log_excerpt": f"pdf_page_fill error: {e}"}
    return {"ok": True, "fill": round(float(fill), 4), "page_cap": page_cap}


TOOL_HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "test_compile": test_compile,
    "page_length": page_length,
}


OPENAI_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "test_compile": {
        "type": "function",
        "function": {
            "name": "test_compile",
            "description": (
                "Compile a piece of LaTeX with pdflatex and report whether it "
                "compiled. Accepts either a complete document (starting with "
                "\\documentclass) or a snippet. Snippets are wrapped in the "
                "SAME preamble as the broken document you are fixing, so a "
                "snippet failure here is a real failure in that document's "
                "context (no false positives from missing packages). Use this "
                "to probe a candidate fix on a tight region before rewriting "
                "the whole document."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "latex": {
                        "type": "string",
                        "description": "LaTeX source — either a full document or a snippet.",
                    }
                },
                "required": ["latex"],
            },
        },
    },
    "page_length": {
        "type": "function",
        "function": {
            "name": "page_length",
            "description": (
                "Compile a complete LaTeX document and measure its rendered "
                "length, returning {ok, fill, page_cap}. `fill` is a decimal "
                "where 1.0 == exactly one page; 1.25 == 25% into a second "
                "page; 0.8 == 80% of one page. Use this to decide whether to "
                "add, tighten, or drop content. Must be a complete document."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "latex": {
                        "type": "string",
                        "description": "Complete LaTeX source starting with \\documentclass.",
                    }
                },
                "required": ["latex"],
            },
        },
    },
}
