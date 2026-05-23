import pytest

from api.generate_resume.render import (
    DEFAULT_TEMPLATE,
    _date_range,
    _is_jinja_template,
    latex_escape,
    pick_template,
    render_resume,
    validate_resume_shape,
)


class TestLatexEscape:
    def test_none_becomes_empty(self):
        assert latex_escape(None) == ""

    def test_backslash_escaped(self):
        # Backslash is replaced first; subsequent passes also escape the
        # braces inside the replacement.
        out = latex_escape("a\\b")
        assert "textbackslash" in out
        assert out.startswith("a") and out.endswith("b")

    def test_special_chars_escaped(self):
        out = latex_escape("a&b%c$d#e_f{g}h~i^j")
        assert "\\&" in out and "\\%" in out and "\\$" in out
        assert "\\#" in out and "\\_" in out and "\\{" in out and "\\}" in out
        assert "\\textasciitilde{}" in out and "\\textasciicircum{}" in out

    def test_smart_quotes_normalized(self):
        out = latex_escape("‘hi’ and “hello”")
        assert "'hi'" in out
        assert "``hello''" in out

    def test_em_dash_to_triple_dash(self):
        assert "---" in latex_escape("a—b")

    def test_non_string_stringified(self):
        assert latex_escape(42) == "42"


class TestDateRange:
    def test_both_set_returns_range(self):
        assert _date_range("2020", "2023") == "2020 -- 2023"

    def test_start_only(self):
        assert _date_range("2020", "") == "2020"

    def test_end_only(self):
        assert _date_range("", "2023") == "2023"

    def test_neither(self):
        assert _date_range("", "") == ""

    def test_strips_whitespace(self):
        assert _date_range("  2020  ", "  2023  ") == "2020 -- 2023"


class TestPickTemplate:
    def test_returns_default_when_no_user_template(self):
        assert pick_template(None) is DEFAULT_TEMPLATE
        assert pick_template("") is DEFAULT_TEMPLATE

    def test_returns_user_template_when_valid_jinja(self):
        custom = "(((header.name)))"
        assert pick_template(custom) == custom

    def test_falls_back_to_default_when_no_jinja_markers(self):
        # Legacy raw LaTeX with no Jinja delimiters
        assert pick_template("\\documentclass{article}") is DEFAULT_TEMPLATE

    def test_is_jinja_template(self):
        assert _is_jinja_template("(((x)))")
        assert _is_jinja_template("((* if x *))")
        assert not _is_jinja_template("plain")
        assert not _is_jinja_template("")


class TestRenderResume:
    def test_renders_header_name_into_output(self, sample_resume_json):
        latex = render_resume(sample_resume_json)
        assert "Ada Lovelace" in latex

    def test_renders_experience_bullets(self, sample_resume_json):
        latex = render_resume(sample_resume_json)
        assert "Wrote first algorithm" in latex

    def test_falls_back_when_user_template_syntax_error(self, sample_resume_json):
        bad_template = "((* if not_closed (((stuff)))"
        # Bad user template falls back to default
        out = render_resume(sample_resume_json, template=bad_template)
        assert "Ada Lovelace" in out

    def test_empty_resume_renders(self):
        out = render_resume({"header": {}, "sections": []})
        assert "\\begin{document}" in out


class TestValidateResumeShape:
    def test_passes_valid(self):
        validate_resume_shape({"sections": [{"kind": "experience"}]})

    def test_rejects_non_dict(self):
        with pytest.raises(ValueError, match="must be an object"):
            validate_resume_shape([])

    def test_rejects_missing_sections(self):
        with pytest.raises(ValueError, match="sections must be an array"):
            validate_resume_shape({})

    def test_rejects_non_dict_section(self):
        with pytest.raises(ValueError, match=r"sections\[0\]"):
            validate_resume_shape({"sections": ["not a dict"]})

    def test_rejects_missing_kind(self):
        with pytest.raises(ValueError, match="kind is required"):
            validate_resume_shape({"sections": [{}]})
