from __future__ import annotations

import pytest

from api.generate_resume import agent_tools


pytestmark = pytest.mark.usefixtures("isolated_app_dir")


class TestDetectShortBullets:
    def test_empty_inputs_return_empty(self):
        assert agent_tools.detect_short_bullets({}, []) == []
        assert agent_tools.detect_short_bullets({"sections": []}, [[]]) == []

    def test_short_tail_detected_when_last_line_underfilled(self):
        resume = {
            "sections": [
                {"kind": "experience", "items": [
                    {"role": "R", "company": "C",
                     "bullets": ["bullet that wraps onto another line short"]},
                ]},
            ],
        }
        lines = [[
            {"text": "bullet that wraps onto another", "width_ratio": 1.0,
             "is_last_on_page": False},
            {"text": "line short", "width_ratio": 0.1, "is_last_on_page": False},
            {"text": "footer", "width_ratio": 0.5, "is_last_on_page": True},
        ]]
        out = agent_tools.detect_short_bullets(resume, lines)
        assert len(out) == 1
        assert out[0]["lines"] == 2
        assert out[0]["last_line_fill"] < 0.35

    def test_excludes_last_line_on_page(self):
        resume = {
            "sections": [
                {"kind": "experience", "items": [
                    {"role": "R", "company": "C", "bullets": ["a b c d e"]},
                ]},
            ],
        }
        # Bullet wraps with short final line, but it's the last on the page
        lines = [[
            {"text": "a b c", "width_ratio": 0.9, "is_last_on_page": False},
            {"text": "d e", "width_ratio": 0.1, "is_last_on_page": True},
        ]]
        out = agent_tools.detect_short_bullets(resume, lines)
        assert out == []

    def test_single_line_bullets_not_flagged(self):
        resume = {
            "sections": [
                {"kind": "experience", "items": [
                    {"role": "R", "company": "C", "bullets": ["one liner"]},
                ]},
            ],
        }
        lines = [[
            {"text": "one liner", "width_ratio": 0.2, "is_last_on_page": False},
            {"text": "trailer", "width_ratio": 0.4, "is_last_on_page": True},
        ]]
        assert agent_tools.detect_short_bullets(resume, lines) == []


class TestPageLengthTool:
    def test_empty_resume_returns_error(self):
        out = agent_tools.page_length(resume={})
        assert out["ok"] is False
        assert "empty or non-object" in out["log_excerpt"]

    def test_invalid_shape_returns_schema_error(self):
        out = agent_tools.page_length(resume={"no_sections": True})
        assert out["ok"] is False
        assert "schema error" in out["log_excerpt"]

    def test_render_error_surfaces(self, mocker):
        mocker.patch(
            "api.generate_resume.agent_tools.render_resume",
            side_effect=RuntimeError("render bug"),
        )
        out = agent_tools.page_length(resume={"sections": [{"kind": "experience"}]})
        assert out["ok"] is False
        assert "render error" in out["log_excerpt"]

    def test_compile_error_returns_log_excerpt(self, mocker):
        mocker.patch(
            "api.generate_resume.agent_tools.render_resume",
            return_value="\\begin{document}hi\\end{document}",
        )
        from api.generate_resume.compile import LatexCompileError
        err = LatexCompileError("boom", log_excerpt="line1\nline2")
        mocker.patch(
            "api.generate_resume.agent_tools.compile_latex",
            side_effect=err,
        )
        out = agent_tools.page_length(resume={"sections": [{"kind": "experience"}]})
        assert out["ok"] is False
        assert "line1" in out["log_excerpt"]

    def test_success_returns_fill_and_cap(self, mocker, tmp_path):
        mocker.patch(
            "api.generate_resume.agent_tools.render_resume",
            return_value="\\begin{document}hi\\end{document}",
        )
        fake_pdf = tmp_path / "x.pdf"
        fake_pdf.write_bytes(b"%PDF")
        mocker.patch(
            "api.generate_resume.agent_tools.compile_latex",
            return_value=fake_pdf,
        )
        mocker.patch(
            "api.generate_resume.agent_tools.pdf_page_metrics",
            return_value={"fill": 0.875, "lines": []},
        )
        out = agent_tools.page_length(
            resume={"sections": [{"kind": "experience"}]},
        )
        assert out["ok"] is True
        assert out["fill"] == 0.875
        assert out["page_cap"] == 1  # default
        assert out["short_bullets"] == []


class TestRegistry:
    def test_tool_handlers_has_page_length(self):
        assert "page_length" in agent_tools.TOOL_HANDLERS

    def test_openai_tool_schemas_has_page_length(self):
        schema = agent_tools.OPENAI_TOOL_SCHEMAS["page_length"]
        # It's a parsed JSON schema from page_length.tool.json
        assert isinstance(schema, dict)
