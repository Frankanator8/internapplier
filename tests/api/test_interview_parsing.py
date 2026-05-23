import pytest

from api.interview_parsing import extract_partial_feedback, parse_grade_payload


class TestParseGradePayload:
    def test_happy_path(self):
        score, fb = parse_grade_payload('{"score": 8.5, "feedback": "good"}')
        assert score == 8.5
        assert fb == "good"

    def test_strips_json_code_fence(self):
        raw = '```json\n{"score": 7, "feedback": "ok"}\n```'
        score, fb = parse_grade_payload(raw)
        assert score == 7.0
        assert fb == "ok"

    def test_missing_keys_raises(self):
        with pytest.raises(ValueError, match="missing required keys"):
            parse_grade_payload('{"score": 5}')

    def test_non_numeric_score_raises(self):
        with pytest.raises(ValueError, match="score not numeric"):
            parse_grade_payload('{"score": "bad", "feedback": "x"}')

    def test_non_string_feedback_coerced(self):
        score, fb = parse_grade_payload('{"score": 5, "feedback": 42}')
        assert fb == "42"

    def test_null_feedback_becomes_empty_string(self):
        score, fb = parse_grade_payload('{"score": 5, "feedback": null}')
        assert fb == ""


class TestExtractPartialFeedback:
    def test_returns_empty_when_no_feedback_key(self):
        assert extract_partial_feedback('{"score": 5}') == ""

    def test_returns_empty_no_colon(self):
        assert extract_partial_feedback('{"feedback"') == ""

    def test_returns_empty_no_open_quote(self):
        assert extract_partial_feedback('{"feedback": 5}') == ""

    def test_extracts_complete_string(self):
        assert extract_partial_feedback('{"feedback": "hello"}') == "hello"

    def test_extracts_incomplete_string(self):
        # No closing quote yet — stream in progress
        assert extract_partial_feedback('{"feedback": "hello wor') == "hello wor"

    def test_decodes_escape_sequences(self):
        assert extract_partial_feedback(r'{"feedback": "a\nb"}') == "a\nb"
        assert extract_partial_feedback(r'{"feedback": "a\tb"}') == "a\tb"
        assert extract_partial_feedback(r'{"feedback": "a\"b"}') == 'a"b'
        assert extract_partial_feedback(r'{"feedback": "a\\b"}') == "a\\b"
        assert extract_partial_feedback(r'{"feedback": "a\/b"}') == "a/b"

    def test_unknown_escape_passes_through(self):
        # \x is not in the escape map — falls back to passing the x through
        assert extract_partial_feedback(r'{"feedback": "a\xb"}') == "axb"
