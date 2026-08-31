from __future__ import annotations

import shutil

import pytest

from api.generate_resume.compile import LatexCompileError
from api.generate_resume.preview import (
    TemplateRenderError,
    _pick,
    compile_template_preview,
)
from api.generate_resume.render import (
    DEFAULT_TEMPLATE,
    pick_template,
    render_with,
    validate_resume_shape,
)
from api.generate_resume.sample_data import SAMPLE_RESUME

needs_pdflatex = pytest.mark.skipif(
    shutil.which("pdflatex") is None, reason="pdflatex not installed"
)

_RAW_LATEX = r"\documentclass{article}\begin{document}hello\end{document}"
_BROKEN_JINJA = "((* if header.name *))" + DEFAULT_TEMPLATE  # unclosed if


class TestSampleResume:
    def test_shape_is_valid(self):
        validate_resume_shape(SAMPLE_RESUME)

    def test_covers_every_section_kind_the_default_template_handles(self):
        kinds = {s["kind"] for s in SAMPLE_RESUME["sections"]}
        assert kinds == {
            "education", "experience", "projects", "skills", "awards", "hobbies",
        }

    def test_experience_items_have_bullets(self):
        exp = next(s for s in SAMPLE_RESUME["sections"] if s["kind"] == "experience")
        assert len(exp["items"]) >= 2
        assert all(len(it["bullets"]) >= 2 for it in exp["items"])

    def test_renders_through_default_template(self):
        latex = render_with(DEFAULT_TEMPLATE, SAMPLE_RESUME)
        assert "Jordan Alvarez" in latex
        assert "Redis read-through" in latex
        # chars that need escaping survive as escaped LaTeX, not raw
        assert r"Cedar \& Bloom" in latex
        assert r"41\%" in latex


class TestPick:
    """The preview must show what generation would actually use."""

    @pytest.mark.parametrize("template", ["", "   ", None, _RAW_LATEX, DEFAULT_TEMPLATE])
    def test_agrees_with_pick_template(self, template):
        chosen, _ = _pick(template)
        assert chosen == pick_template(template)

    def test_blank_template_is_noted(self):
        chosen, note = _pick("")
        assert chosen == DEFAULT_TEMPLATE
        assert "empty" in note

    def test_non_jinja_template_is_noted(self):
        chosen, note = _pick(_RAW_LATEX)
        assert chosen == DEFAULT_TEMPLATE
        assert "markers" in note

    def test_valid_template_has_no_note(self):
        chosen, note = _pick(DEFAULT_TEMPLATE)
        assert chosen == DEFAULT_TEMPLATE
        assert note is None


class TestCompileTemplatePreview:
    def test_jinja_syntax_error_raises_instead_of_falling_back(self):
        """render_resume() deliberately falls back to the default template on a
        syntax error; preview must surface the error instead."""
        with pytest.raises(TemplateRenderError):
            compile_template_preview(_BROKEN_JINJA)

    @needs_pdflatex
    def test_blank_template_compiles_the_default(self):
        pdf, note = compile_template_preview("")
        assert pdf.exists()
        assert pdf.suffix == ".pdf"
        assert note is not None

    @needs_pdflatex
    def test_valid_template_compiles_with_no_note(self):
        pdf, note = compile_template_preview(DEFAULT_TEMPLATE)
        assert pdf.exists()
        assert note is None

    @needs_pdflatex
    def test_successive_compiles_use_distinct_paths(self):
        """QWebEngineView caches by URL — a reused path would show a stale PDF."""
        first, _ = compile_template_preview(DEFAULT_TEMPLATE)
        second, _ = compile_template_preview(DEFAULT_TEMPLATE)
        assert first != second
        assert second.exists()

    @needs_pdflatex
    def test_broken_latex_raises_compile_error(self):
        broken = DEFAULT_TEMPLATE.replace(r"\begin{center}", r"\begin{center", 1)
        with pytest.raises(LatexCompileError):
            compile_template_preview(broken)
