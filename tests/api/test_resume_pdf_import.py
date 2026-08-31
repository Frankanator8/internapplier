"""Tests for the resume-PDF importer."""
from __future__ import annotations

import pytest

from api.resume_pdf_import import (
    MAX_BULLETS_PER_ENTRY,
    MAX_BULLET_CHARS,
    MAX_FLAT_ITEMS,
    MAX_TEXT_CHARS,
    NoTextInPdfError,
    ResumePdfError,
    extract_text,
    is_empty,
    normalize_extraction,
    parse_text,
    summarize,
)


class _FakePage:
    def __init__(self, text: str, *, layout_supported: bool = True):
        self._text = text
        self._layout_supported = layout_supported

    def extract_text(self, **kwargs):
        if kwargs.get("extraction_mode") and not self._layout_supported:
            raise TypeError("unexpected keyword argument 'extraction_mode'")
        return self._text


class _FakeReader:
    def __init__(self, pages, *, encrypted: bool = False, decrypts: bool = True):
        self.pages = pages
        self.is_encrypted = encrypted
        self._decrypts = decrypts

    def decrypt(self, password):
        return 1 if self._decrypts else 0


def _reader(mocker, reader):
    # extract_text does a function-local `from pypdf import PdfReader`, so the
    # patch has to land on the source module.
    return mocker.patch("pypdf.PdfReader", return_value=reader)


_FILLER = "Ada Lovelace — Software Engineer. " * 10  # comfortably over the floor


class TestExtractText:
    def test_joins_pages_with_a_blank_line(self, mocker):
        """Section adjacency is what the model reads — page order must survive."""
        _reader(mocker, _FakeReader([_FakePage(_FILLER), _FakePage("EDUCATION\nMIT")]))
        out = extract_text("resume.pdf")
        assert out.endswith("EDUCATION\nMIT")
        assert "\n\nEDUCATION" in out

    def test_falls_back_to_plain_mode_when_layout_is_unsupported(self, mocker):
        """A pypdf pinned below 4.x has no extraction_mode kwarg."""
        _reader(mocker, _FakeReader([_FakePage(_FILLER, layout_supported=False)]))
        assert _FILLER.strip() in extract_text("resume.pdf")

    def test_scanned_pdf_raises_before_any_llm_call(self, mocker):
        """No OCR is bundled, so bail early rather than bill the user for a
        request that can only return an empty resume."""
        _reader(mocker, _FakeReader([_FakePage(""), _FakePage("   ")]))
        with pytest.raises(NoTextInPdfError, match="no selectable text"):
            extract_text("scan.pdf")

    def test_encrypted_pdf_raises_a_friendly_error(self, mocker):
        _reader(mocker, _FakeReader([_FakePage(_FILLER)], encrypted=True, decrypts=False))
        with pytest.raises(ResumePdfError, match="password-protected"):
            extract_text("locked.pdf")

    def test_encrypted_pdf_with_an_empty_password_still_reads(self, mocker):
        _reader(mocker, _FakeReader([_FakePage(_FILLER)], encrypted=True, decrypts=True))
        assert extract_text("locked.pdf")

    def test_unreadable_file_is_wrapped_in_resume_pdf_error(self, mocker):
        """A raw pypdf traceback must never reach a QMessageBox."""
        mocker.patch("pypdf.PdfReader", side_effect=Exception("not a pdf"))
        with pytest.raises(ResumePdfError, match="Couldn't open that PDF"):
            extract_text("notes.txt")

    def test_oversized_text_is_truncated_to_the_cap(self, mocker):
        page = _FakePage("word " * (MAX_TEXT_CHARS // 2))
        _reader(mocker, _FakeReader([page]))
        out = extract_text("cv.pdf")
        assert len(out) <= MAX_TEXT_CHARS + len("\n\n[…truncated]")
        assert out.endswith("[…truncated]")

    def test_a_page_that_fails_entirely_is_skipped(self, mocker):
        class _Broken:
            def extract_text(self, **kwargs):
                raise RuntimeError("boom")

        _reader(mocker, _FakeReader([_Broken(), _FakePage(_FILLER)]))
        assert _FILLER.strip() in extract_text("resume.pdf")


class TestNormalizeExtraction:
    def test_general_info_keeps_only_line_fields(self):
        """COMBO_FIELDS are enums GeneralInfoPage.load() silently discards on a
        near-miss, and they cover work authorization and EEO answers."""
        out = normalize_extraction({
            "general_info": {"email": "a@b.c", "work_authorization": "US Citizen"},
        })
        assert out["general_info"] == {"email": "a@b.c"}

    def test_general_info_drops_empty_values(self):
        out = normalize_extraction({"general_info": {"email": "a@b.c", "phone": "  "}})
        assert out["general_info"] == {"email": "a@b.c"}

    def test_experience_without_company_or_title_is_dropped(self):
        out = normalize_extraction({"experience": [
            {"company": "", "title": "", "bullets": ["something"]},
            {"company": "Acme", "title": ""},
        ]})
        assert [e["company"] for e in out["experience"]] == ["Acme"]

    def test_unknown_category_becomes_relevant(self):
        """ExperiencePage falls back to 'relevant' for unknown categories —
        normalizing here keeps the store and the UI in agreement."""
        out = normalize_extraction({"experience": [
            {"company": "A", "title": "X", "category": "volunteering"},
            {"company": "B", "title": "Y", "category": "OTHER"},
        ]})
        assert [e["category"] for e in out["experience"]] == ["relevant", "other"]

    def test_bullets_are_stringified_and_empties_dropped(self):
        out = normalize_extraction({"projects": [
            {"name": "P", "bullets": ["ok", "", None, 42]},
        ]})
        assert out["projects"][0]["bullets"] == ["ok", "42"]

    def test_courses_gain_an_empty_skills_list(self):
        """CoursesWidget reads courses[].skills unconditionally."""
        out = normalize_extraction({"education": [
            {"school": "MIT", "courses": [{"name": "Algorithms", "grade": "A"}]},
        ]})
        assert out["education"][0]["courses"] == [
            {"name": "Algorithms", "grade": "A", "skills": []}
        ]

    def test_course_without_a_name_is_dropped(self):
        out = normalize_extraction({"education": [
            {"school": "MIT", "courses": [{"grade": "A"}, {"name": "Algo"}]},
        ]})
        assert [c["name"] for c in out["education"][0]["courses"]] == ["Algo"]

    def test_education_without_a_school_is_dropped(self):
        out = normalize_extraction({"education": [{"degree": "B.S."}]})
        assert out["education"] == []

    def test_award_without_a_title_is_dropped(self):
        out = normalize_extraction({"awards": [{"issuer": "IEEE"}, {"title": "Prize"}]})
        assert [a["title"] for a in out["awards"]] == ["Prize"]

    def test_skills_are_deduped_case_insensitively_in_order(self):
        out = normalize_extraction({"skills": ["Python", "go", "python", "Go", "Rust"]})
        assert out["skills"] == ["Python", "go", "Rust"]

    def test_missing_top_level_keys_become_empty_containers(self):
        """The review dialog and the merge both index every section key."""
        out = normalize_extraction({})
        assert out == {
            "general_info": {}, "experience": [], "projects": [], "education": [],
            "awards": [], "skills": [], "hobbies": [],
        }

    def test_non_dict_input_is_tolerated(self):
        assert normalize_extraction(["nope"])["experience"] == []

    def test_non_dict_entries_in_a_list_are_skipped(self):
        out = normalize_extraction({"projects": ["a string", {"name": "P"}]})
        assert [p["name"] for p in out["projects"]] == ["P"]

    def test_wrong_typed_sections_are_tolerated(self):
        out = normalize_extraction({"skills": "Python, Go", "experience": {"a": 1}})
        assert out["skills"] == []
        assert out["experience"] == []

    def test_bullet_and_skill_counts_are_capped(self):
        out = normalize_extraction({
            "experience": [{
                "company": "A", "title": "X",
                "bullets": ["b"] * (MAX_BULLETS_PER_ENTRY + 5),
            }],
            "skills": [f"s{i}" for i in range(MAX_FLAT_ITEMS + 10)],
        })
        assert len(out["experience"][0]["bullets"]) == MAX_BULLETS_PER_ENTRY
        assert len(out["skills"]) == MAX_FLAT_ITEMS

    def test_a_runaway_bullet_is_truncated(self):
        out = normalize_extraction({"awards": [{"title": "T", "bullets": ["x" * 5000]}]})
        assert len(out["awards"][0]["bullets"][0]) == MAX_BULLET_CHARS


class TestSummarizeAndIsEmpty:
    def test_summary_lists_each_section_count(self):
        data = normalize_extraction({
            "experience": [{"company": "A", "title": "X"}],
            "skills": ["Python", "Go"],
        })
        assert summarize(data) == "1 experience · 0 projects · 0 education · 0 awards · 2 skills"

    def test_summary_notes_identity_when_general_info_is_present(self):
        data = normalize_extraction({"general_info": {"email": "a@b.c"}})
        assert summarize(data).endswith("+ identity")

    def test_is_empty_true_when_everything_is_blank(self):
        assert is_empty(normalize_extraction({}))

    def test_is_empty_false_when_only_general_info_is_present(self):
        """Contact details alone are still worth importing."""
        assert not is_empty(normalize_extraction({"general_info": {"email": "a@b.c"}}))


class _StubProvider:
    def __init__(self, payload):
        self.payload = payload
        self.seen = None

    def extract_resume(self, text):
        self.seen = text
        return self.payload


class TestParseText:
    def test_calls_the_provider_and_normalizes_the_result(self):
        stub = _StubProvider({"skills": ["Python", "python"], "bogus_key": 1})
        out = parse_text("resume text", provider=stub)
        assert stub.seen == "resume text"
        assert out["skills"] == ["Python"]
        assert "bogus_key" not in out

    def test_provider_errors_propagate(self):
        class _Boom:
            def extract_resume(self, text):
                raise ValueError("AI returned unexpected format — please try again.")

        with pytest.raises(ValueError, match="unexpected format"):
            parse_text("text", provider=_Boom())
