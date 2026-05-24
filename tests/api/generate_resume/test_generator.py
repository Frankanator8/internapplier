"""End-to-end-ish tests for ResumeGenerator, using a mocked provider so
no real AI calls happen."""
from __future__ import annotations

import json
import pathlib

import pytest

from api.generate_resume import generator as gen_mod
from api.generate_resume import persist as persist_mod
from api.generate_resume.generator import (
    ResumeGenerator,
    _apply_label_drops,
    _build_feedback,
    _build_header_from_general_info,
    _build_pdf_filename,
    _clean_for_filename,
    _extract_json_object,
    _norm,
    _persist_pdf,
)


pytestmark = pytest.mark.usefixtures("isolated_app_dir")


class TestNormAndExtract:
    def test_norm_collapses_whitespace_and_lowercases(self):
        assert _norm("  HELLO   World ") == "hello world"

    def test_norm_empty(self):
        assert _norm("") == ""
        assert _norm(None) == ""

    def test_extract_json_object_balanced(self):
        text = 'prose {"a": 1, "b": {"c": 2}} trailing'
        assert _extract_json_object(text) == '{"a": 1, "b": {"c": 2}}'

    def test_extract_json_object_no_brace(self):
        assert _extract_json_object("no braces here") is None

    def test_extract_json_object_handles_string_with_brace(self):
        # Braces inside strings should not affect depth
        text = '{"a": "v{}{}", "b": 1}'
        assert _extract_json_object(text) == text

    def test_extract_json_object_handles_escapes(self):
        text = '{"a": "\\""}'  # JSON: {"a": "\""}
        # ensure it extracts a balanced JSON
        extracted = _extract_json_object(text)
        assert extracted == text


class TestCleanForFilename:
    def test_strips_fs_unsafe_chars(self):
        out = _clean_for_filename('a/b\\c<d>e:"f|g?h*i')
        for ch in '/\\<>:"|?*':
            assert ch not in out

    def test_collapses_whitespace_and_strips(self):
        assert _clean_for_filename("  hello   world  ") == "hello world"


class TestBuildPdfFilename:
    def test_company_and_title(self):
        assert _build_pdf_filename("Acme", "Software Engineer") == "Acme - Software Engine.pdf"

    def test_company_only(self):
        assert _build_pdf_filename("Acme", None) == "Acme.pdf"

    def test_title_only(self):
        assert _build_pdf_filename(None, "Engineer") == "Engineer.pdf"

    def test_neither_falls_back(self):
        assert _build_pdf_filename(None, None) == "resume.pdf"


class TestApplyLabelDrops:
    def test_no_drops_returns_shallow_copies(self):
        profile = {"experience": [{"role": "X", "company": "C"}]}
        out = _apply_label_drops(profile, set())
        assert out["experience"] == profile["experience"]
        assert out["experience"] is not profile["experience"]

    def test_drops_matched_experience(self):
        profile = {
            "experience": [
                {"role": "Engineer", "company": "Acme"},
                {"role": "PM", "company": "Beta"},
            ],
            "projects": [],
            "awards": [],
            "education": [],
        }
        out = _apply_label_drops(profile, {_norm("engineer @ acme")})
        assert len(out["experience"]) == 1
        assert out["experience"][0]["role"] == "PM"

    def test_drops_courses_case_insensitive(self):
        profile = {
            "education": [{"school": "MIT", "courses": ["Algorithms", "DB Systems"]}],
            "experience": [], "projects": [], "awards": [],
        }
        out = _apply_label_drops(profile, {_norm("algorithms")})
        assert out["education"][0]["courses"] == ["DB Systems"]


class TestBuildHeader:
    def test_uses_preferred_name(self):
        gi = {"preferred_name": "Ada", "first_name": "Augusta", "last_name": "X"}
        assert _build_header_from_general_info(gi)["name"] == "Ada"

    def test_falls_back_to_first_last(self):
        gi = {"first_name": "Ada", "last_name": "Lovelace"}
        assert _build_header_from_general_info(gi)["name"] == "Ada Lovelace"

    def test_builds_links(self):
        gi = {"linkedin": "https://li", "github": "https://gh"}
        hdr = _build_header_from_general_info(gi)
        assert {"label": "LinkedIn", "url": "https://li"} in hdr["links"]
        assert {"label": "GitHub", "url": "https://gh"} in hdr["links"]

    def test_combines_location(self):
        gi = {"city": "London", "country": "UK"}
        assert _build_header_from_general_info(gi)["location"] == "London, UK"


class TestBuildFeedback:
    def test_no_problems_returns_none(self):
        assert _build_feedback(None, 0.5, True, 1, [], None, True) is None

    def test_compile_error_included(self):
        out = _build_feedback("bad", None, False, 1, [], None, False)
        assert "FAILED TO COMPILE" in out
        assert "bad" in out

    def test_page_overflow_with_drops(self):
        out = _build_feedback(None, 1.4, False, 1, ["a", "b"], None, False)
        assert "PAGE OVERFLOW" in out
        assert "a; b" in out

    def test_grader_feedback_when_score_low(self):
        grade = {"feedback": "needs work", "score": 5}
        out = _build_feedback(None, 0.5, True, 1, [], grade, False)
        assert "GRADER FEEDBACK" in out
        assert "needs work" in out


class TestPersistPdf:
    def test_no_src_returns_none_tuple(self):
        assert _persist_pdf(None, None) == (None, None, False)

    def test_explicit_dest_copies_to_target(self, tmp_path):
        src = tmp_path / "src.pdf"
        src.write_bytes(b"%PDF")
        dest = tmp_path / "out" / "x.pdf"
        written, desired, collided = _persist_pdf(src, dest)
        assert written == dest and desired == dest
        assert collided is False
        assert dest.exists()

    def test_collision_appends_uuid(self, tmp_path, monkeypatch):
        src = tmp_path / "src.pdf"
        src.write_bytes(b"%PDF")
        out_dir = tmp_path / "outdir"
        out_dir.mkdir()
        existing = out_dir / "Acme.pdf"
        existing.write_bytes(b"prev")
        monkeypatch.setattr(persist_mod, "get_resume_output_dir", lambda: out_dir)
        written, desired, collided = _persist_pdf(src, None, company="Acme")
        assert collided is True
        assert desired == existing
        assert written != existing
        assert written.exists()


class TestResumeGeneratorIntegration:
    def test_succeeds_first_attempt(self, mocker, sample_profile, sample_jd, tmp_path):
        # Stub all external calls
        mocker.patch(
            "api.ai_provider.keyword_extractor.extract_jd_keywords",
            return_value={"keywords": [], "excerpts": []},
        )
        mocker.patch(
            "api.ai_provider.keyword_extractor.format_jd_signals",
            return_value="signals",
        )

        resume_json = {
            "sections": [{"kind": "experience", "items": [
                {"role": "X", "company": "C", "bullets": ["b"]},
            ]}],
        }

        class FakeProv:
            def generate_resume_stream(self, *args, **kwargs):
                yield json.dumps(resume_json)

            def grade_resume_stream(self, *args, **kwargs):
                yield json.dumps({"score": 9.9, "feedback": "great", "drops": []})

        # Stub compile + metrics
        fake_pdf = tmp_path / "out.pdf"
        fake_pdf.write_bytes(b"%PDF")
        mocker.patch.object(gen_mod, "compile_latex", return_value=fake_pdf)
        mocker.patch.object(
            gen_mod, "pdf_page_metrics",
            return_value={"fill": 0.5, "lines": [[]]},
        )

        # Stub settings to keep loop short
        mocker.patch.object(gen_mod, "get_resume_page_cap", return_value=1)
        mocker.patch.object(gen_mod, "get_max_generation_attempts", return_value=3)
        mocker.patch.object(gen_mod, "get_resume_score_threshold", return_value=9.0)
        mocker.patch("api.ai_provider.get_resume_template", return_value="")
        mocker.patch.object(persist_mod, "get_resume_output_dir",
                            return_value=tmp_path / "outdir")

        gen = ResumeGenerator(sample_profile, sample_jd, {}, provider=FakeProv())
        result = gen.generate_latex(company="Acme", job_title="Eng")
        assert result["chosen_attempt"] == 1
        assert result["grade"]["score"] == 9.9
        assert result["pdf"] is not None

    def test_feedback_fed_into_second_attempt(
            self, mocker, sample_profile, sample_jd, tmp_path):
        mocker.patch(
            "api.ai_provider.keyword_extractor.extract_jd_keywords",
            return_value={"keywords": [], "excerpts": []},
        )
        mocker.patch(
            "api.ai_provider.keyword_extractor.format_jd_signals",
            return_value="signals",
        )

        resume_json = {"sections": [{"kind": "experience", "items": [
            {"role": "X", "company": "C", "bullets": ["b"]}]}]}

        provider_calls: list[dict] = []

        class FakeProv:
            def __init__(self):
                self._scores = iter([5.0, 9.9])

            def generate_resume_stream(self, profile, jd, feedback=None,
                                       previous_resume=None, today=None,
                                       company_research=None):
                provider_calls.append({
                    "feedback": feedback, "previous_resume": previous_resume,
                })
                yield json.dumps(resume_json)

            def grade_resume_stream(self, *a, **kw):
                score = next(self._scores)
                yield json.dumps({"score": score, "feedback": "fix it", "drops": []})

        fake_pdf = tmp_path / "out.pdf"
        fake_pdf.write_bytes(b"%PDF")
        mocker.patch.object(gen_mod, "compile_latex", return_value=fake_pdf)
        mocker.patch.object(
            gen_mod, "pdf_page_metrics",
            return_value={"fill": 0.5, "lines": [[]]},
        )
        mocker.patch.object(gen_mod, "get_resume_page_cap", return_value=1)
        mocker.patch.object(gen_mod, "get_max_generation_attempts", return_value=2)
        mocker.patch.object(gen_mod, "get_resume_score_threshold", return_value=9.0)
        mocker.patch("api.ai_provider.get_resume_template", return_value="")
        mocker.patch.object(persist_mod, "get_resume_output_dir",
                            return_value=tmp_path / "outdir")

        gen = ResumeGenerator(sample_profile, sample_jd, {}, provider=FakeProv())
        result = gen.generate_latex()
        assert result["chosen_attempt"] == 2
        # Second call should have feedback from first grade
        assert provider_calls[0]["feedback"] is None
        assert provider_calls[1]["feedback"] is not None
        assert "fix it" in provider_calls[1]["feedback"]
        assert provider_calls[1]["previous_resume"] == resume_json

    def test_returns_best_attempt_when_max_exhausted(
            self, mocker, sample_profile, sample_jd, tmp_path):
        mocker.patch(
            "api.ai_provider.keyword_extractor.extract_jd_keywords",
            return_value={"keywords": [], "excerpts": []},
        )
        mocker.patch(
            "api.ai_provider.keyword_extractor.format_jd_signals",
            return_value="signals",
        )

        resume_json = {"sections": [{"kind": "experience", "items": [
            {"role": "X", "company": "C", "bullets": ["b"]}]}]}

        class FakeProv:
            def generate_resume_stream(self, *a, **kw):
                yield json.dumps(resume_json)

            def grade_resume_stream(self, *a, **kw):
                yield json.dumps({"score": 6.0, "feedback": "meh", "drops": []})

        fake_pdf = tmp_path / "out.pdf"
        fake_pdf.write_bytes(b"%PDF")
        mocker.patch.object(gen_mod, "compile_latex", return_value=fake_pdf)
        mocker.patch.object(
            gen_mod, "pdf_page_metrics",
            return_value={"fill": 0.5, "lines": [[]]},
        )
        mocker.patch.object(gen_mod, "get_resume_page_cap", return_value=1)
        mocker.patch.object(gen_mod, "get_max_generation_attempts", return_value=2)
        mocker.patch.object(gen_mod, "get_resume_score_threshold", return_value=9.0)
        mocker.patch("api.ai_provider.get_resume_template", return_value="")
        mocker.patch.object(persist_mod, "get_resume_output_dir",
                            return_value=tmp_path / "outdir")

        gen = ResumeGenerator(sample_profile, sample_jd, {}, provider=FakeProv())
        result = gen.generate_latex()
        assert result["chosen_attempt"] in (1, 2)  # picks best
        assert result["grade"]["score"] == 6.0
        assert len(result["attempts"]) == 2

    def test_strips_code_fence_from_resume_json(
            self, mocker, sample_profile, sample_jd, tmp_path):
        mocker.patch(
            "api.ai_provider.keyword_extractor.extract_jd_keywords",
            return_value={"keywords": [], "excerpts": []},
        )
        mocker.patch(
            "api.ai_provider.keyword_extractor.format_jd_signals",
            return_value="signals",
        )

        resume_json = {"sections": [{"kind": "experience", "items": [
            {"role": "X", "company": "C", "bullets": ["b"]}]}]}

        class FakeProv:
            def generate_resume_stream(self, *a, **kw):
                yield "```json\n" + json.dumps(resume_json) + "\n```"

            def grade_resume_stream(self, *a, **kw):
                yield json.dumps({"score": 9.9, "feedback": "ok", "drops": []})

        fake_pdf = tmp_path / "out.pdf"
        fake_pdf.write_bytes(b"%PDF")
        mocker.patch.object(gen_mod, "compile_latex", return_value=fake_pdf)
        mocker.patch.object(
            gen_mod, "pdf_page_metrics",
            return_value={"fill": 0.5, "lines": [[]]},
        )
        mocker.patch.object(gen_mod, "get_resume_page_cap", return_value=1)
        mocker.patch.object(gen_mod, "get_max_generation_attempts", return_value=1)
        mocker.patch.object(gen_mod, "get_resume_score_threshold", return_value=9.0)
        mocker.patch("api.ai_provider.get_resume_template", return_value="")
        mocker.patch.object(persist_mod, "get_resume_output_dir",
                            return_value=tmp_path / "outdir")

        gen = ResumeGenerator(sample_profile, sample_jd, {}, provider=FakeProv())
        result = gen.generate_latex()
        assert result["chosen_attempt"] == 1
