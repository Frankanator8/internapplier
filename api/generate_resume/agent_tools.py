from __future__ import annotations

import logging
from typing import Any, Callable

from ..ai_provider import load_schema
from ..constants import AGENT_MAX_LOG_EXCERPT
from .compile import (
    LatexCompileError,
    compile_latex,
    pdf_page_fill,
)

logger = logging.getLogger(__name__)

_MINIMAL_PREAMBLE = r"""\documentclass[11pt]{article}
\usepackage[margin=0.75in]{geometry}
\usepackage{hyperref}
\usepackage{enumitem}
\usepackage{titlesec}
\begin{document}
"""
_MINIMAL_POSTAMBLE = "\n\\end{document}\n"


def _wrap_if_snippet(latex: str) -> str:
    if "\\documentclass" in latex:
        return latex
    return _MINIMAL_PREAMBLE + latex + _MINIMAL_POSTAMBLE


def _truncate(text: str, limit: int = AGENT_MAX_LOG_EXCERPT) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n…[truncated {len(text) - limit} chars]"


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
    "page_length": page_length,
}


OPENAI_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "page_length": load_schema("page_length.tool.json"),
}
