from __future__ import annotations

import shutil

import pytest

from api.ai_provider import default_prompt
from api.generate_resume.compile import LatexCompileError
from api.generate_resume.preview import compile_template_preview

needs_pdflatex = pytest.mark.skipif(
    shutil.which("pdflatex") is None, reason="pdflatex not installed"
)

_RAW_LATEX = r"\documentclass{article}\begin{document}hello\end{document}"


class TestCompileTemplatePreview:
    @needs_pdflatex
    def test_blank_template_compiles_the_default(self):
        pdf, note = compile_template_preview("")
        assert pdf.exists()
        assert pdf.suffix == ".pdf"
        assert note is not None
        assert "empty" in note

    @needs_pdflatex
    def test_whitespace_only_template_compiles_the_default(self):
        pdf, note = compile_template_preview("   \n  ")
        assert pdf.exists()
        assert note is not None

    @needs_pdflatex
    def test_valid_template_compiles_with_no_note(self):
        pdf, note = compile_template_preview(_RAW_LATEX)
        assert pdf.exists()
        assert note is None

    @needs_pdflatex
    def test_default_template_compiles(self):
        pdf, note = compile_template_preview(default_prompt("resume_template.txt"))
        assert pdf.exists()
        assert note is None

    @needs_pdflatex
    def test_successive_compiles_use_distinct_paths(self):
        """QWebEngineView caches by URL — a reused path would show a stale PDF."""
        first, _ = compile_template_preview(_RAW_LATEX)
        second, _ = compile_template_preview(_RAW_LATEX)
        assert first != second
        assert second.exists()

    @needs_pdflatex
    def test_broken_latex_raises_compile_error(self):
        broken = _RAW_LATEX.replace(r"\begin{document}", r"\begin{documen")
        with pytest.raises(LatexCompileError):
            compile_template_preview(broken)
