from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from api.generate_resume import compile as cm
from api.generate_resume.compile import (
    LatexCompileError,
    _extract_error_excerpt,
    _preflight_latex,
    _scrub_smart_chars,
    compile_latex,
    extract_document,
    pdf_page_metrics,
)


class TestExtractDocument:
    def test_extracts_between_documentclass_and_end_document(self):
        s = "junk\n\\documentclass{article}\nhi\n\\end{document}\nafter"
        out = extract_document(s)
        assert out.startswith("\\documentclass")
        assert out.endswith("\\end{document}")

    def test_returns_none_when_no_documentclass(self):
        assert extract_document("just prose") is None

    def test_truncated_returns_from_documentclass_to_eof(self):
        # No \end{document} — return from \documentclass onward
        s = "pre\n\\documentclass{article}\nstuff"
        out = extract_document(s)
        assert out == "\\documentclass{article}\nstuff"

    def test_ignores_documentclass_without_brace(self):
        # Bare mention like "see \documentclass" should NOT match
        assert extract_document("see `\\documentclass` in prose") is None


class TestScrubSmartChars:
    def test_replaces_smart_quotes_and_dashes(self):
        out = _scrub_smart_chars("‘a’ — “b”")
        assert "'" in out and "---" in out and "``" in out

    def test_no_change_when_no_smart_chars(self):
        s = "plain ascii"
        assert _scrub_smart_chars(s) == s


class TestPreflightLatex:
    def test_missing_begin_document(self):
        with pytest.raises(LatexCompileError, match=r"\\begin\{document\}"):
            _preflight_latex("\\end{document}")

    def test_missing_end_document(self):
        with pytest.raises(LatexCompileError, match=r"\\end\{document\}"):
            _preflight_latex("\\begin{document}")

    def test_unbalanced_extra_close_brace(self):
        latex = "\\begin{document}}\\end{document}"
        with pytest.raises(LatexCompileError, match="extra"):
            _preflight_latex(latex)

    def test_unbalanced_unclosed_open_brace(self):
        latex = "\\begin{document}{\\end{document}"
        with pytest.raises(LatexCompileError, match="unclosed"):
            _preflight_latex(latex)

    def test_escaped_braces_dont_count(self):
        latex = "\\begin{document}\\{ \\}\\end{document}"
        _preflight_latex(latex)  # should not raise

    def test_comment_skipped(self):
        latex = "\\begin{document}% comment with } unbalanced\n\\end{document}"
        _preflight_latex(latex)  # comment is skipped to newline


class TestCompileLatex:
    def test_raises_when_pdflatex_not_on_path(self, mocker):
        mocker.patch("api.generate_resume.compile.shutil.which",
                     return_value=None)
        with pytest.raises(LatexCompileError, match="pdflatex not found"):
            compile_latex("\\begin{document}hi\\end{document}")

    def test_returns_pdf_path_on_success(self, mocker, tmp_path):
        mocker.patch("api.generate_resume.compile.shutil.which",
                     return_value="/usr/bin/pdflatex")
        # Simulate two successful pdflatex passes and a produced PDF.
        def fake_run(cmd, **kwargs):
            # workdir is the -output-directory argument
            workdir = Path(cmd[cmd.index("-output-directory") + 1])
            (workdir / "resume.pdf").write_bytes(b"%PDF-1.4")
            return subprocess.CompletedProcess(args=cmd, returncode=0,
                                                stdout="", stderr="")
        mocker.patch("api.generate_resume.compile.subprocess.run",
                     side_effect=fake_run)
        out = compile_latex(
            "\\documentclass{article}\\begin{document}hi\\end{document}",
            workdir=tmp_path,
        )
        assert out == tmp_path / "resume.pdf"
        assert out.exists()

    def test_raises_with_log_excerpt_on_failure(self, mocker, tmp_path):
        mocker.patch("api.generate_resume.compile.shutil.which",
                     return_value="/usr/bin/pdflatex")
        log_text = "blah\n! Undefined control sequence\nl.5 \\foo\nmore\n"
        (tmp_path / "resume.log").write_text(log_text)

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(args=cmd, returncode=1,
                                                stdout="oops", stderr="")
        mocker.patch("api.generate_resume.compile.subprocess.run",
                     side_effect=fake_run)
        with pytest.raises(LatexCompileError) as exc:
            compile_latex(
                "\\documentclass{article}\\begin{document}hi\\end{document}",
                workdir=tmp_path,
            )
        assert "Undefined control sequence" in exc.value.log_excerpt

    def test_timeout_raises(self, mocker, tmp_path):
        mocker.patch("api.generate_resume.compile.shutil.which",
                     return_value="/usr/bin/pdflatex")
        mocker.patch("api.generate_resume.compile.subprocess.run",
                     side_effect=subprocess.TimeoutExpired("pdflatex", 60))
        with pytest.raises(LatexCompileError, match="timed out"):
            compile_latex(
                "\\documentclass{article}\\begin{document}hi\\end{document}",
                workdir=tmp_path,
            )


class TestExtractErrorExcerpt:
    def test_returns_around_error_marker(self):
        text = "\n".join(["intro1", "intro2", "intro3", "intro4",
                          "! big error", "context1", "context2"])
        out = _extract_error_excerpt(text)
        assert "! big error" in out
        assert "context1" in out
        # Should include a couple lines before
        assert "intro3" in out

    def test_no_marker_returns_tail(self):
        text = "x\n" * 200
        out = _extract_error_excerpt(text, max_chars=10)
        assert len(out) <= 10


class TestPdfPageMetrics:
    def test_zero_pages_returns_zero_fill(self, mocker):
        class _FakeReader:
            pages = []
        mocker.patch("pypdf.PdfReader", return_value=_FakeReader())
        out = pdf_page_metrics(Path("/nowhere/x.pdf"))
        assert out == {"fill": 0.0, "lines": []}
