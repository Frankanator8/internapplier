from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from api.generate_resume.compile import (
    LatexCompileError,
    _extract_error_excerpt,
    _preflight_latex,
    _scrub_smart_chars,
    compile_latex,
    extract_document,
    pdf_page_metrics,
    pdf_plain_text,
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


class _FakeMetricsPage:
    """Minimal stand-in for a pypdf page: replays fixed (x, y, text,
    font_size) fragments through a `visitor_text` callback, one fragment
    per line."""

    def __init__(self, height: float, lines: list[tuple[float, str, float, float]]):
        self._lines = lines
        self.mediabox = SimpleNamespace(height=height)

    def extract_text(self, visitor_text=None, **_kwargs):
        if visitor_text is not None:
            for y, text, font_size, x in self._lines:
                tm = [1, 0, 0, 1, x, y]
                visitor_text(text, None, tm, None, font_size)
        return ""


class _FakeMetricsReader:
    def __init__(self, pages: list[_FakeMetricsPage]):
        self.pages = pages


def _line(y: float, text: str = "line text", font_size: float = 10.0, x: float = 50.0):
    return (y, text, font_size, x)


class TestPdfPageMetricsGeometricFill:
    """`fill` must measure content height against the page's real text
    area, not against line density within the content's own span — see
    api/generate_resume/compile.py for why the old formula was wrong."""

    def test_full_page_reads_close_to_one(self, mocker):
        lines = [_line(y) for y in range(90, 0, -10)]  # 90, 80, ..., 10
        pages = [_FakeMetricsPage(100.0, lines)]
        mocker.patch("pypdf.PdfReader", return_value=_FakeMetricsReader(pages))
        out = pdf_page_metrics(Path("/nowhere/x.pdf"))
        assert out["fill"] == pytest.approx(1.0, abs=1e-6)

    def test_large_section_gaps_still_reads_full(self, mocker):
        # Same top/bottom extent as the full page above, but only 4 widely
        # and irregularly spaced lines. Internal spacing must not matter
        # once the content still spans margin-to-margin.
        pages = [_FakeMetricsPage(100.0, [_line(90), _line(60), _line(30), _line(10)])]
        mocker.patch("pypdf.PdfReader", return_value=_FakeMetricsReader(pages))
        out = pdf_page_metrics(Path("/nowhere/x.pdf"))
        assert out["fill"] == pytest.approx(1.0, abs=1e-6)

    def test_half_empty_page_reads_well_below_one(self, mocker):
        pages = [_FakeMetricsPage(100.0, [
            _line(90), _line(80), _line(70), _line(60), _line(55),
        ])]
        mocker.patch("pypdf.PdfReader", return_value=_FakeMetricsReader(pages))
        out = pdf_page_metrics(Path("/nowhere/x.pdf"))
        assert out["fill"] == pytest.approx(0.4375, abs=1e-6)

    def test_second_page_single_trailing_line_exceeds_one(self, mocker):
        page0_lines = [_line(y) for y in range(90, 0, -10)]
        pages = [
            _FakeMetricsPage(100.0, page0_lines),
            _FakeMetricsPage(100.0, [_line(95)]),
        ]
        mocker.patch("pypdf.PdfReader", return_value=_FakeMetricsReader(pages))
        out = pdf_page_metrics(Path("/nowhere/x.pdf"))
        assert out["fill"] > 1.0

    def test_width_ratio_ignores_left_indent(self, mocker):
        # Fallback char-advance ratio is 0.5 (no calibration pairs since
        # each line here is a single fragment), so at font_size=10 each
        # character advances 5pt. Both lines are built to reach the same
        # x_end=400 even though line 2 starts far more indented (x=200
        # vs x=50) — mimicking a deeply-indented wrapped bullet line that
        # still reaches the right margin. Under the old "width over
        # widest line" ratio, the indented line's raw span (400-200=200)
        # would score ~0.57 against the header's span (400-50=350),
        # unfairly reading as a short trailing line. The column-relative
        # ratio only cares how far right the text reaches, so both must
        # score ~1.0.
        pages = [_FakeMetricsPage(100.0, [
            _line(90, text="H" * 70, x=50.0),
            _line(80, text="B" * 40, x=200.0),
        ])]
        mocker.patch("pypdf.PdfReader", return_value=_FakeMetricsReader(pages))
        out = pdf_page_metrics(Path("/nowhere/x.pdf"))
        lines = out["lines"][0]
        assert lines[0]["width_ratio"] == pytest.approx(1.0, abs=1e-6)
        assert lines[1]["width_ratio"] == pytest.approx(1.0, abs=1e-6)

    def test_footer_page_number_does_not_corrupt_fill(self, mocker):
        # LaTeX's default `\pagestyle{plain}` draws a page number in the
        # footer unless the document disables it. It is always isolated
        # from the body by a gap far larger than body line spacing —
        # here 3 body lines 12pt apart near the top, then a lone "1" at
        # y=5, a 61pt gap away. Left uncorrected this drags the inferred
        # "bottom of content" down to the footer, reading the page as
        # nearly full regardless of the 3-line body.
        pages = [_FakeMetricsPage(100.0, [
            _line(90), _line(78), _line(66), _line(5, text="1"),
        ])]
        mocker.patch("pypdf.PdfReader", return_value=_FakeMetricsReader(pages))
        out = pdf_page_metrics(Path("/nowhere/x.pdf"))
        # top_margin=10, mirrored bottom_margin=10, usable=80;
        # min_y_last (footer excluded) = 66; used=(100-10)-66=24 -> 0.3.
        assert out["fill"] == pytest.approx(0.3, abs=1e-6)
        texts = [ln["text"] for ln in out["lines"][0]]
        assert "1" not in texts

    def test_isolated_footer_alone_is_not_misread_as_full_content(self, mocker):
        # A trailing page holding only a stray footer number (no real
        # body content) has too few lines (<2) to be geometrically
        # distinguished from real content, so it's kept — but this must
        # not regress into always reading whole numbers for real content
        # pages elsewhere in the document (covered by the test above).
        page0_lines = [_line(y) for y in range(90, 0, -10)]
        pages = [
            _FakeMetricsPage(100.0, page0_lines),
            _FakeMetricsPage(100.0, [_line(24, text="2")]),
        ]
        mocker.patch("pypdf.PdfReader", return_value=_FakeMetricsReader(pages))
        out = pdf_page_metrics(Path("/nowhere/x.pdf"))
        assert out["fill"] > 0.0


class _FakePage:
    def __init__(self, text: str, *, layout_supported: bool = True):
        self._text = text
        self._layout_supported = layout_supported

    def extract_text(self, **kwargs):
        if kwargs.get("extraction_mode") and not self._layout_supported:
            raise TypeError("unexpected keyword argument 'extraction_mode'")
        return self._text


class _FakeReader:
    def __init__(self, pages):
        self.pages = pages


class TestPdfPlainText:
    def test_joins_pages_with_a_blank_line(self, mocker):
        mocker.patch(
            "pypdf.PdfReader",
            return_value=_FakeReader([_FakePage("Ada Lovelace"), _FakePage("EDUCATION\nMIT")]),
        )
        out = pdf_plain_text(Path("resume.pdf"))
        assert out.endswith("EDUCATION\nMIT")
        assert "\n\nEDUCATION" in out

    def test_falls_back_to_plain_mode_when_layout_is_unsupported(self, mocker):
        mocker.patch(
            "pypdf.PdfReader",
            return_value=_FakeReader([_FakePage("Ada Lovelace", layout_supported=False)]),
        )
        assert "Ada Lovelace" in pdf_plain_text(Path("resume.pdf"))

    def test_a_page_that_fails_entirely_is_skipped(self, mocker):
        class _Broken:
            def extract_text(self, **kwargs):
                raise RuntimeError("boom")

        mocker.patch(
            "pypdf.PdfReader",
            return_value=_FakeReader([_Broken(), _FakePage("Ada Lovelace")]),
        )
        assert "Ada Lovelace" in pdf_plain_text(Path("resume.pdf"))

    def test_unreadable_file_returns_empty_string(self, mocker):
        mocker.patch("pypdf.PdfReader", side_effect=Exception("not a pdf"))
        assert pdf_plain_text(Path("notes.txt")) == ""

    def test_collapses_long_blank_runs(self, mocker):
        mocker.patch(
            "pypdf.PdfReader",
            return_value=_FakeReader([_FakePage("A\n\n\n\n\nB")]),
        )
        out = pdf_plain_text(Path("resume.pdf"))
        assert "\n\n\n" not in out
