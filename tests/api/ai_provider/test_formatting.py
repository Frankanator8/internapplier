from api.ai_provider.formatting import (
    TOOL_EVENT_PREFIX,
    _format_context,
    _format_tool_event,
    _profile_json,
    strip_code_fence,
)


def test_tool_event_prefix_is_record_separator():
    assert TOOL_EVENT_PREFIX == "\x1e"


class TestStripCodeFence:
    def test_returns_input_when_no_fence(self):
        assert strip_code_fence("plain text") == "plain text"

    def test_strips_closed_generic_fence(self):
        raw = "preamble\n```\ninner content\n```\ntrailing"
        assert strip_code_fence(raw) == "inner content"

    def test_strips_closed_json_hint_fence(self):
        raw = '```json\n{"a": 1}\n```'
        assert strip_code_fence(raw, lang_hints=("json",)) == '{"a": 1}'

    def test_strips_unclosed_json_fence(self):
        raw = '```json\n{"a": 1}'
        # No closing fence — should still extract content
        out = strip_code_fence(raw, lang_hints=("json",))
        assert out == '{"a": 1}'

    def test_hint_match_is_case_insensitive(self):
        raw = "```JSON\n{}\n```"
        assert strip_code_fence(raw, lang_hints=("json",)) == "{}"

    def test_hint_does_not_match_other_lang(self):
        # If hint doesn't match, generic fence stripping should still work
        raw = "```python\nprint(1)\n```"
        assert strip_code_fence(raw, lang_hints=("json",)) == "print(1)"


class TestProfileJson:
    def test_keeps_only_known_keys(self):
        out = _profile_json({
            "experience": [{"x": 1}],
            "projects": [],
            "education": [],
            "awards": [],
            "skills": [],
            "hobbies": [],
            "general_info": {"first_name": "ignored"},  # not in _PROFILE_KEYS
            "extra": "discarded",
        })
        import json
        obj = json.loads(out)
        assert set(obj.keys()) == {"experience", "projects", "education",
                                   "awards", "skills", "hobbies"}
        assert obj["experience"] == [{"x": 1}]

    def test_defaults_missing_keys_to_empty_list(self):
        import json
        obj = json.loads(_profile_json({}))
        for k in ("experience", "projects", "education", "awards", "skills", "hobbies"):
            assert obj[k] == []


class TestFormatToolEvent:
    def test_ok_page_length_includes_fill_and_cap(self):
        out = _format_tool_event(
            "page_length", 1, {"latex": "abc"}, {"ok": True, "fill": 0.95, "page_cap": 1},
        )
        assert "✓" in out and "page_length" in out
        assert "fill=0.950 / page_cap=1" in out
        assert "latex=3 chars" in out

    def test_ok_non_page_length_summary(self):
        out = _format_tool_event("other", 2, {}, {"ok": True})
        assert "✓" in out
        assert "→ ok" in out

    def test_failure_emits_excerpt(self):
        out = _format_tool_event(
            "page_length", 1, {}, {"ok": False, "log_excerpt": "line1\nline2"},
        )
        assert "✗" in out and "failed:" in out
        assert "line1" in out and "line2" in out

    def test_failure_with_no_excerpt(self):
        out = _format_tool_event("x", 1, {}, {"ok": False})
        assert "failed" in out

    def test_non_numeric_fill_is_handled(self):
        out = _format_tool_event(
            "page_length", 1, {}, {"ok": True, "fill": "n/a", "page_cap": 1},
        )
        # No exception, falls back to repr
        assert "fill=n/a" in out


class TestFormatContext:
    def test_experience(self):
        out = _format_context({"type": "experience", "company": "Acme", "role": "SWE"})
        assert "Acme" in out and "SWE" in out

    def test_project(self):
        out = _format_context({"type": "project", "name": "MyApp"})
        assert "MyApp" in out

    def test_education(self):
        out = _format_context({"type": "education", "school": "MIT", "degree": "BS"})
        assert "MIT" in out and "BS" in out

    def test_unknown_type_returns_empty(self):
        assert _format_context({"type": "other"}) == ""
        assert _format_context({}) == ""
