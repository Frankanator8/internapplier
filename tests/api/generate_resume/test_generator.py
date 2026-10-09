"""End-to-end-ish tests for ResumeGenerator, using a mocked provider so
no real AI calls happen."""
from __future__ import annotations

import json

import pytest

_SAMPLE_LATEX = r"""\documentclass{article}
\begin{document}
\section*{Experience}
\textbf{X @ C}
\begin{itemize}
\item b
\end{itemize}
\end{document}
"""

_SAMPLE_RESUME_TEXT = "Experience\nX @ C\n- b"

from api.generate_resume import generator as gen_mod
from api.generate_resume import persist as persist_mod
from api.generate_resume.generator import ResumeGenerator
from api.generate_resume.json_recovery import (
    extract_json_object as _extract_json_object,
    norm as _norm,
)
from api.generate_resume.persist import (
    _build_pdf_filename,
    _clean_for_filename,
    apply_label_drops as _apply_label_drops,
    build_feedback as _build_feedback,
    build_header_from_general_info as _build_header_from_general_info,
    move_persisted_resume as _move_persisted_resume,
    persist_pdf as _persist_pdf,
    read_tex_sidecar as _read_tex_sidecar,
    tex_sidecar as _tex_sidecar,
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
        assert _build_feedback(None, 0.9, True, 1, [], None, True) is None

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
        out = _build_feedback(None, 0.9, True, 1, [], grade, False)
        assert "GRADER FEEDBACK" in out
        assert "needs work" in out

    def test_underfilled_when_below_target(self):
        out = _build_feedback(None, 0.5, True, 1, [], None, True)
        assert "UNDERFILLED" in out
        assert "0.50" in out

    def test_underfilled_suggests_restoring_drops(self):
        out = _build_feedback(None, 0.5, True, 1, ["Old Job @ Corp"], None, True)
        assert "UNDERFILLED" in out
        assert "Old Job @ Corp" in out

    def test_not_underfilled_when_at_or_above_target(self):
        out = _build_feedback(None, 0.9, True, 1, [], None, True)
        assert out is None

    def test_underfill_skipped_on_page_overflow(self):
        # Overflow message should win; underfill branch must not also fire.
        out = _build_feedback(None, 1.4, False, 1, [], None, False)
        assert "PAGE OVERFLOW" in out
        assert "UNDERFILLED" not in out


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
        assert not _tex_sidecar(dest).exists()

    def test_latex_writes_sidecar_next_to_pdf(self, tmp_path):
        src = tmp_path / "src.pdf"
        src.write_bytes(b"%PDF")
        dest = tmp_path / "out" / "x.pdf"
        written, _, _ = _persist_pdf(src, dest, latex=_SAMPLE_LATEX)
        sidecar = _tex_sidecar(written)
        assert sidecar.is_file()
        assert sidecar.read_text(encoding="utf-8") == _SAMPLE_LATEX
        assert _read_tex_sidecar(written) == _SAMPLE_LATEX

    def test_empty_latex_does_not_create_sidecar(self, tmp_path):
        src = tmp_path / "src.pdf"
        src.write_bytes(b"%PDF")
        dest = tmp_path / "x.pdf"
        _persist_pdf(src, dest, latex="")
        assert not _tex_sidecar(dest).exists()

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

    def test_collision_writes_sidecar_next_to_suffixed_pdf(self, tmp_path, monkeypatch):
        src = tmp_path / "src.pdf"
        src.write_bytes(b"%PDF")
        out_dir = tmp_path / "outdir"
        out_dir.mkdir()
        existing = out_dir / "Acme.pdf"
        existing.write_bytes(b"prev")
        (out_dir / "Acme.tex").write_text("old", encoding="utf-8")
        monkeypatch.setattr(persist_mod, "get_resume_output_dir", lambda: out_dir)
        written, desired, collided = _persist_pdf(
            src, None, company="Acme", latex=_SAMPLE_LATEX,
        )
        assert collided is True
        assert _tex_sidecar(written).read_text(encoding="utf-8") == _SAMPLE_LATEX
        assert _tex_sidecar(desired).read_text(encoding="utf-8") == "old"

    def test_move_persisted_resume_replaces_dest_and_removes_src(self, tmp_path):
        dest_pdf = tmp_path / "Acme.pdf"
        dest_pdf.write_bytes(b"old-pdf")
        dest_tex = tmp_path / "Acme.tex"
        dest_tex.write_text("old-tex", encoding="utf-8")
        src_pdf = tmp_path / "Acme-abcd1234.pdf"
        src_pdf.write_bytes(b"new-pdf")
        src_tex = tmp_path / "Acme-abcd1234.tex"
        src_tex.write_text("new-tex", encoding="utf-8")

        _move_persisted_resume(src_pdf, dest_pdf)

        assert dest_pdf.read_bytes() == b"new-pdf"
        assert dest_tex.read_text(encoding="utf-8") == "new-tex"
        assert not src_pdf.exists()
        assert not src_tex.exists()

    def test_move_persisted_resume_drops_stale_dest_sidecar(self, tmp_path):
        dest_pdf = tmp_path / "Acme.pdf"
        dest_pdf.write_bytes(b"old-pdf")
        dest_tex = tmp_path / "Acme.tex"
        dest_tex.write_text("old-tex", encoding="utf-8")
        src_pdf = tmp_path / "Acme-abcd1234.pdf"
        src_pdf.write_bytes(b"new-pdf")

        _move_persisted_resume(src_pdf, dest_pdf)

        assert dest_pdf.read_bytes() == b"new-pdf"
        assert not dest_tex.exists()
        assert not src_pdf.exists()


class TestResumeGeneratorIntegration:
    def test_succeeds_first_attempt(self, mocker, sample_profile, sample_jd, tmp_path):
        grade_calls: list[str] = []

        class FakeProv:
            def generate_resume_stream(self, *args, **kwargs):
                yield _SAMPLE_LATEX

            def grade_resume_stream(self, resume_text, *args, **kwargs):
                grade_calls.append(resume_text)
                yield json.dumps({"score": 9.9, "feedback": "great", "drops": []})

        # Stub compile + metrics
        fake_pdf = tmp_path / "out.pdf"
        fake_pdf.write_bytes(b"%PDF")
        mocker.patch.object(gen_mod, "compile_latex", return_value=fake_pdf)
        mocker.patch.object(
            gen_mod, "pdf_page_metrics",
            return_value={"fill": 0.5, "lines": [[]]},
        )
        mocker.patch.object(
            gen_mod, "pdf_plain_text", return_value=_SAMPLE_RESUME_TEXT,
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
        sidecar = _tex_sidecar(result["pdf"])
        assert sidecar.is_file()
        assert sidecar.read_text(encoding="utf-8")
        # The grader must receive the extracted plain text, not the LaTeX source.
        assert grade_calls == [_SAMPLE_RESUME_TEXT]

    def test_feedback_fed_into_second_attempt(
            self, mocker, sample_profile, sample_jd, tmp_path):
        provider_calls: list[dict] = []

        class FakeProv:
            def __init__(self):
                self._scores = iter([5.0, 9.9])

            def generate_resume_stream(self, profile, jd, feedback=None,
                                       previous_latex=None, today=None,
                                       company_research=None):
                provider_calls.append({
                    "feedback": feedback, "previous_latex": previous_latex,
                })
                yield _SAMPLE_LATEX

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
        mocker.patch.object(
            gen_mod, "pdf_plain_text", return_value=_SAMPLE_RESUME_TEXT,
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
        assert provider_calls[1]["previous_latex"].rstrip() == _SAMPLE_LATEX.rstrip()

    def test_returns_best_attempt_when_max_exhausted(
            self, mocker, sample_profile, sample_jd, tmp_path):
        class FakeProv:
            def generate_resume_stream(self, *a, **kw):
                yield _SAMPLE_LATEX

            def grade_resume_stream(self, *a, **kw):
                yield json.dumps({"score": 6.0, "feedback": "meh", "drops": []})

        fake_pdf = tmp_path / "out.pdf"
        fake_pdf.write_bytes(b"%PDF")
        mocker.patch.object(gen_mod, "compile_latex", return_value=fake_pdf)
        mocker.patch.object(
            gen_mod, "pdf_page_metrics",
            return_value={"fill": 0.5, "lines": [[]]},
        )
        mocker.patch.object(
            gen_mod, "pdf_plain_text", return_value=_SAMPLE_RESUME_TEXT,
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

    def test_strips_code_fence_from_latex(
            self, mocker, sample_profile, sample_jd, tmp_path):
        class FakeProv:
            def generate_resume_stream(self, *a, **kw):
                yield "```latex\n" + _SAMPLE_LATEX + "\n```"

            def grade_resume_stream(self, *a, **kw):
                yield json.dumps({"score": 9.9, "feedback": "ok", "drops": []})

        fake_pdf = tmp_path / "out.pdf"
        fake_pdf.write_bytes(b"%PDF")
        mocker.patch.object(gen_mod, "compile_latex", return_value=fake_pdf)
        mocker.patch.object(
            gen_mod, "pdf_page_metrics",
            return_value={"fill": 0.5, "lines": [[]]},
        )
        mocker.patch.object(
            gen_mod, "pdf_plain_text", return_value=_SAMPLE_RESUME_TEXT,
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

    def test_compile_failure_skips_grading(
            self, mocker, sample_profile, sample_jd, tmp_path):
        """No PDF means no ATS-extractable text, so the grader is never called
        — there's nothing meaningful to grade."""
        grade_calls: list[str] = []

        class FakeProv:
            def generate_resume_stream(self, *a, **kw):
                yield _SAMPLE_LATEX

            def grade_resume_stream(self, resume_text, *a, **kw):
                grade_calls.append(resume_text)
                yield json.dumps({"score": 9.9, "feedback": "ok", "drops": []})

        mocker.patch.object(
            gen_mod, "compile_latex",
            side_effect=gen_mod.LatexCompileError("boom", log_excerpt="! boom"),
        )
        mocker.patch.object(gen_mod, "get_resume_page_cap", return_value=1)
        mocker.patch.object(gen_mod, "get_max_generation_attempts", return_value=1)
        mocker.patch.object(gen_mod, "get_resume_score_threshold", return_value=9.0)
        mocker.patch("api.ai_provider.get_resume_template", return_value="")
        mocker.patch.object(persist_mod, "get_resume_output_dir",
                            return_value=tmp_path / "outdir")

        gen = ResumeGenerator(sample_profile, sample_jd, {}, provider=FakeProv())
        result = gen.generate_latex()
        assert grade_calls == []
        assert result["grade"] is None
        assert result["pdf"] is None
