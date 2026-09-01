from __future__ import annotations

import pytest

from api.generate_resume import agent_tools


pytestmark = pytest.mark.usefixtures("isolated_app_dir")

_BULLET = "bullet that wraps onto another line short"


class TestDetectShortBullets:
    def test_empty_inputs_return_empty(self):
        assert agent_tools.detect_short_bullets("", []) == []
        assert agent_tools.detect_short_bullets(r"\item nothing", []) == []

    def test_short_tail_detected_when_last_line_underfilled(self):
        latex = r"\begin{itemize}\item " + _BULLET + r"\end{itemize}"
        lines = [[
            {"text": "bullet that wraps onto another", "width_ratio": 1.0,
             "is_last_on_page": False},
            {"text": "line short", "width_ratio": 0.1, "is_last_on_page": False},
            {"text": "footer", "width_ratio": 0.5, "is_last_on_page": True},
        ]]
        out = agent_tools.detect_short_bullets(latex, lines)
        assert len(out) == 1
        assert out[0]["lines"] == 2
        assert out[0]["last_line_fill"] < 0.35

    def test_excludes_last_line_on_page(self):
        latex = r"\item a b c d e"
        lines = [[
            {"text": "a b c", "width_ratio": 0.9, "is_last_on_page": False},
            {"text": "d e", "width_ratio": 0.1, "is_last_on_page": True},
        ]]
        out = agent_tools.detect_short_bullets(latex, lines)
        assert out == []

    def test_single_line_bullets_not_flagged(self):
        latex = r"\item one liner"
        lines = [[
            {"text": "one liner", "width_ratio": 0.2, "is_last_on_page": False},
            {"text": "trailer", "width_ratio": 0.4, "is_last_on_page": True},
        ]]
        assert agent_tools.detect_short_bullets(latex, lines) == []

    def test_strips_textbf_when_matching(self):
        latex = r"\item \textbf{wraps onto another line short}"
        lines = [[
            {"text": "wraps onto another", "width_ratio": 1.0,
             "is_last_on_page": False},
            {"text": "line short", "width_ratio": 0.1, "is_last_on_page": False},
            {"text": "footer", "width_ratio": 0.5, "is_last_on_page": True},
        ]]
        out = agent_tools.detect_short_bullets(latex, lines)
        assert len(out) == 1


class TestFillAccepts:
    def test_in_range(self):
        assert agent_tools.fill_accepts(0.9, 1, 0.9)
        assert agent_tools.fill_accepts(1.0, 1, 0.9)
        assert agent_tools.fill_accepts(0.95, 1, 0.9)

    def test_overflow_and_underfill(self):
        assert not agent_tools.fill_accepts(1.001, 1, 0.9)
        assert not agent_tools.fill_accepts(0.89, 1, 0.9)

    def test_invalid_values(self):
        assert not agent_tools.fill_accepts("n/a", 1, 0.9)
        assert not agent_tools.fill_accepts(None, 1, 0.9)


class TestPageLengthTool:
    def test_empty_latex_returns_error(self):
        out = agent_tools.page_length(latex="")
        assert out["ok"] is False
        assert "empty latex" in out["log_excerpt"]

    def test_non_string_returns_error(self):
        out = agent_tools.page_length(latex={"sections": []})
        assert out["ok"] is False
        assert "empty latex" in out["log_excerpt"]

    def test_compile_error_returns_log_excerpt(self, mocker):
        from api.generate_resume.compile import LatexCompileError
        err = LatexCompileError("boom", log_excerpt="line1\nline2")
        mocker.patch(
            "api.generate_resume.agent_tools.compile_latex",
            side_effect=err,
        )
        out = agent_tools.page_length(latex=r"\documentclass{article}\begin{document}x\end{document}")
        assert out["ok"] is False
        assert "line1" in out["log_excerpt"]

    def test_success_returns_fill_and_cap(self, mocker, tmp_path):
        fake_pdf = tmp_path / "x.pdf"
        fake_pdf.write_bytes(b"%PDF")
        mocker.patch(
            "api.generate_resume.agent_tools.compile_latex",
            return_value=fake_pdf,
        )
        mocker.patch(
            "api.generate_resume.agent_tools.pdf_page_metrics",
            return_value={"fill": 0.95, "lines": []},
        )
        out = agent_tools.page_length(
            latex=r"\documentclass{article}\begin{document}hi\end{document}",
        )
        assert out["ok"] is True
        assert out["fill"] == 0.95
        assert out["page_cap"] == 1  # default
        assert out["target_fill"] == agent_tools.RESUME_TARGET_FILL
        assert out["done"] is True
        assert out["short_bullets"] == []

    def test_overflow_is_not_done(self, mocker, tmp_path):
        fake_pdf = tmp_path / "x.pdf"
        fake_pdf.write_bytes(b"%PDF")
        mocker.patch(
            "api.generate_resume.agent_tools.compile_latex",
            return_value=fake_pdf,
        )
        mocker.patch(
            "api.generate_resume.agent_tools.pdf_page_metrics",
            return_value={"fill": 1.073, "lines": []},
        )
        out = agent_tools.page_length(
            latex=r"\documentclass{article}\begin{document}hi\end{document}",
        )
        assert out["ok"] is True
        assert out["done"] is False

    def test_underfill_is_not_done(self, mocker, tmp_path):
        fake_pdf = tmp_path / "x.pdf"
        fake_pdf.write_bytes(b"%PDF")
        mocker.patch(
            "api.generate_resume.agent_tools.compile_latex",
            return_value=fake_pdf,
        )
        mocker.patch(
            "api.generate_resume.agent_tools.pdf_page_metrics",
            return_value={"fill": 0.5, "lines": []},
        )
        out = agent_tools.page_length(
            latex=r"\documentclass{article}\begin{document}hi\end{document}",
        )
        assert out["done"] is False

    def test_done_suppresses_short_bullets(self, mocker, tmp_path):
        fake_pdf = tmp_path / "x.pdf"
        fake_pdf.write_bytes(b"%PDF")
        mocker.patch(
            "api.generate_resume.agent_tools.compile_latex",
            return_value=fake_pdf,
        )
        mocker.patch(
            "api.generate_resume.agent_tools.pdf_page_metrics",
            return_value={"fill": 1.0, "lines": [[{"text": "x"}]]},
        )
        detect = mocker.patch(
            "api.generate_resume.agent_tools.detect_short_bullets",
            return_value=[{"text": "wasted", "lines": 2, "last_line_fill": 0.1}],
        )
        out = agent_tools.page_length(
            latex=r"\documentclass{article}\begin{document}hi\end{document}",
        )
        assert out["done"] is True
        assert out["short_bullets"] == []
        detect.assert_not_called()

    def test_snippet_without_documentclass_is_wrapped(self, mocker, tmp_path):
        fake_pdf = tmp_path / "x.pdf"
        fake_pdf.write_bytes(b"%PDF")
        compile_mock = mocker.patch(
            "api.generate_resume.agent_tools.compile_latex",
            return_value=fake_pdf,
        )
        mocker.patch(
            "api.generate_resume.agent_tools.pdf_page_metrics",
            return_value={"fill": 0.5, "lines": []},
        )
        agent_tools.page_length(latex=r"\section*{X}")
        sent = compile_mock.call_args[0][0]
        assert r"\documentclass" in sent
        assert r"\section*{X}" in sent


class TestRegistry:
    def test_tool_handlers_has_page_length(self):
        assert "page_length" in agent_tools.TOOL_HANDLERS

    def test_openai_tool_schemas_has_page_length(self):
        from api.ai_provider import load_schema
        schema = load_schema("page_length.tool.json")
        assert isinstance(schema, dict)
        assert schema["function"]["name"] == "page_length"
        assert schema["function"]["parameters"]["required"] == ["latex"]
