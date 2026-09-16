from __future__ import annotations

import shutil

import pytest

from api.generate_resume.manual_render import (
    compile_manual_preview,
    escape_latex,
    render_manual_resume,
)
from api.generate_resume.persist import build_header_from_general_info

needs_pdflatex = pytest.mark.skipif(
    shutil.which("pdflatex") is None, reason="pdflatex not installed"
)


class TestEscapeLatex:
    def test_escapes_special_characters(self):
        out = escape_latex(r"R&D_50% $100 #1 {x} ~ ^ \foo")
        assert r"\&" in out
        assert r"\_" in out
        assert r"\%" in out
        assert r"\$" in out
        assert r"\#" in out
        assert r"\{" in out
        assert r"\}" in out
        assert r"\textbackslash{}" in out
        assert r"\textasciitilde{}" in out
        assert r"\textasciicircum{}" in out

    def test_empty_and_none(self):
        assert escape_latex("") == ""
        assert escape_latex(None) == ""


def _header():
    return build_header_from_general_info({
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.com",
        "phone": "555-0100",
        "linkedin": "linkedin.com/in/ada",
        "github": "https://github.com/ada",
        "city": "London",
        "country": "UK",
    })


def _sections():
    return [
        {
            "title": "Education",
            "items": [{
                "kind": "education",
                "data": {
                    "school": "University of London",
                    "degree": "B.S. Mathematics",
                    "start": "1840",
                    "end": "1843",
                    "gpa": "4.0/4.0",
                    "courses": [{"name": "Analysis"}, {"name": "Algebra"}],
                },
            }],
        },
        {
            "title": "Relevant Experience",
            "items": [{
                "kind": "experience",
                "data": {
                    "title": "Analyst",
                    "company": "R&D Labs",
                    "start": "Jun 1843",
                    "end": "Present",
                    "bullets": ["Wrote the first algorithm", "Impact: 100% coverage"],
                },
            }],
        },
        {
            "title": "Projects",
            "items": [{
                "kind": "project",
                "data": {
                    "name": "Analytical Engine",
                    "url": "https://example.com/engine",
                    "start": "1842",
                    "end": "1843",
                    "skills": ["Math", "Notes"],
                    "bullets": ["Described a general-purpose computer"],
                },
            }],
        },
        {
            "title": "Technical Skills",
            "items": [{
                "kind": "skills",
                "data": {"items": ["Python", "C++"], "label": "Languages"},
            }],
        },
        {
            "title": "Empty",
            "items": [],
        },
    ]


class TestRenderManualResume:
    def test_includes_header_contact_and_sections(self):
        latex = render_manual_resume(_header(), _sections())
        assert r"\documentclass" in latex
        assert r"\begin{document}" in latex
        assert r"\end{document}" in latex
        assert "Ada Lovelace" in latex
        assert "ada@example.com" in latex
        assert r"\section{Education}" in latex
        assert r"\section{Relevant Experience}" in latex
        assert r"\section{Projects}" in latex
        assert r"\section{Technical Skills}" in latex
        assert r"\section{Empty}" not in latex
        assert "University of London" in latex
        assert "Analyst" in latex
        assert r"R\&D Labs" in latex
        assert "Wrote the first algorithm" in latex
        assert r"100\% coverage" in latex
        assert "Analytical Engine" in latex
        assert r"\textbf{Python}" in latex

    def test_omits_empty_sections_keeps_header_only(self):
        latex = render_manual_resume(_header(), [{"title": "Nope", "items": []}])
        assert "Ada Lovelace" in latex
        assert r"\section{Nope}" not in latex


@needs_pdflatex
class TestCompileManualPreview:
    def test_renders_and_compiles(self):
        latex = render_manual_resume(_header(), _sections())
        pdf = compile_manual_preview(latex)
        assert pdf.exists()
        assert pdf.suffix == ".pdf"

    def test_successive_compiles_use_distinct_paths(self):
        latex = render_manual_resume(_header(), [])
        first = compile_manual_preview(latex)
        second = compile_manual_preview(latex)
        assert first != second
        assert second.exists()
