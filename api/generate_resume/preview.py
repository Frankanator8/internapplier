"""Compile a resume template to PDF using bundled sample data.

Lets the template editor in Settings show what a template actually produces
without running the LLM pipeline. Fallback rules mirror generation
(:func:`pick_template`) so the preview reflects what a real run would use —
except that a Jinja syntax error in the user's own template is raised rather
than silently swallowed into the default template.
"""
from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from jinja2 import TemplateError

from .compile import LatexCompileError, compile_latex
from .render import DEFAULT_TEMPLATE, _is_jinja_template, render_with
from .sample_data import SAMPLE_RESUME

logger = logging.getLogger(__name__)

_EMPTY_NOTE = (
    "Template is empty — previewing the built-in default template, "
    "which is what resume generation would use."
)
_NOT_JINJA_NOTE = (
    "Template has no ((( ))) or ((* *)) markers, so it can't be filled with "
    "resume data — previewing the built-in default template instead."
)

_preview_dir: Path | None = None
_preview_counter = 0


class TemplateRenderError(RuntimeError):
    """The template itself is invalid Jinja (before LaTeX ever ran)."""


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


def _pick(template: str | None) -> tuple[str, str | None]:
    """Same choice :func:`pick_template` makes, plus why — so the preview can
    tell the user their template was skipped instead of quietly showing the
    default. `test_preview.py` asserts the two stay in agreement."""
    src = template or ""
    if not src.strip():
        return DEFAULT_TEMPLATE, _EMPTY_NOTE
    if not _is_jinja_template(src):
        return DEFAULT_TEMPLATE, _NOT_JINJA_NOTE
    return src, None


def compile_template_preview(template: str) -> tuple[Path, str | None]:
    """Render `template` with :data:`SAMPLE_RESUME` and compile it to PDF.

    Returns ``(pdf_path, note)`` where `note` is a user-facing message when
    the template was not usable and the built-in default was previewed
    instead, else ``None``.

    Raises :class:`TemplateRenderError` for Jinja problems and
    :class:`~.compile.LatexCompileError` for LaTeX problems.
    """
    chosen, note = _pick(template)
    try:
        latex = render_with(chosen, SAMPLE_RESUME)
    except TemplateError as exc:
        logger.info("compile_template_preview — template render failed: %s", exc)
        raise TemplateRenderError(f"Template error: {exc}") from exc

    pdf = compile_latex(latex, workdir=_next_pdf_dir())
    logger.info("compile_template_preview — rendered preview at %s", pdf)
    return pdf, note


__all__ = [
    "LatexCompileError",
    "TemplateRenderError",
    "compile_template_preview",
]
