"""Compile a resume template to PDF as-is.

Lets the template editor in Settings show what a template actually produces
without running the LLM pipeline. An empty template previews the bundled
default (``prompts/resume_template.txt``) so the preview reflects what
generation would fall back to when the user has no saved template.
"""
from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from api.ai_provider import default_prompt

from .compile import LatexCompileError, compile_latex

logger = logging.getLogger(__name__)

_EMPTY_NOTE = "Template is empty — previewing the built-in default template."

_preview_dir: Path | None = None
_preview_counter = 0


def _next_pdf_dir() -> Path:
    """A fresh sub-directory per compile.

    QWebEngineView caches by URL, so reusing one path would show a stale PDF.
    The previous compile's directory is removed to keep temp usage bounded.
    """
    global _preview_dir, _preview_counter

    if _preview_dir is None:
        _preview_dir = Path(tempfile.mkdtemp(prefix="tmpl_preview_"))

    prev = _preview_dir / f"run_{_preview_counter}"
    _preview_counter += 1
    out = _preview_dir / f"run_{_preview_counter}"
    out.mkdir(parents=True, exist_ok=True)

    if prev.exists():
        shutil.rmtree(prev, ignore_errors=True)
    return out


def compile_template_preview(template: str) -> tuple[Path, str | None]:
    """Compile `template` to PDF as-is.

    Returns ``(pdf_path, note)`` where `note` is a user-facing message when
    the template was empty and the built-in default was previewed instead,
    else ``None``.

    Raises :class:`~.compile.LatexCompileError` for LaTeX problems.
    """
    src = (template or "").strip()
    note = None
    if not src:
        src = default_prompt("resume_template.txt")
        note = _EMPTY_NOTE

    pdf = compile_latex(src, workdir=_next_pdf_dir())
    logger.info("compile_template_preview — compiled preview at %s", pdf)
    return pdf, note


__all__ = [
    "LatexCompileError",
    "compile_template_preview",
]
