from __future__ import annotations

import io
import zipfile

from api.linkedin_import import (
    _bullets_from_description,
    _extract_websites,
    _get,
    parse_zip,
    summarize,
)


class TestBulletsFromDescription:
    def test_splits_on_bullets_and_newlines(self):
        text = "• one\n• two\n   three"
        assert _bullets_from_description(text) == ["one", "two", "three"]

    def test_empty_returns_empty(self):
        assert _bullets_from_description("") == []

    def test_strips_leading_dash(self):
        assert _bullets_from_description("- alpha\n- beta") == ["alpha", "beta"]


class TestExtractWebsites:
    def test_picks_linkedin_and_github(self):
        blob = "Find me at https://linkedin.com/in/x and https://github.com/y"
        linkedin, github = _extract_websites(blob)
        assert "linkedin.com" in linkedin
        assert "github.com" in github

    def test_no_matches_empty(self):
        assert _extract_websites("nothing here") == ("", "")


class TestGet:
    def test_case_insensitive_first_non_empty(self):
        row = {"Email Address": "x@y.com", "email": ""}
        assert _get(row, "EMAIL ADDRESS") == "x@y.com"

    def test_skips_empty_returns_next(self):
        row = {"a": "", "b": "  ", "c": "v"}
        assert _get(row, "a", "b", "c") == "v"

    def test_no_match_empty(self):
        assert _get({"a": "v"}, "z") == ""


def _build_csv(rows: list[dict]) -> str:
    import csv
    if not rows:
        return ""
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    return out.getvalue()


def _make_zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


class TestParseZip:
    def test_parses_positions_into_experience(self, tmp_path):
        positions = _build_csv([{
            "Company Name": "Acme",
            "Title": "Engineer",
            "Started On": "2020",
            "Finished On": "2023",
            "Description": "• Built X\n• Shipped Y",
        }])
        zip_path = tmp_path / "data.zip"
        zip_path.write_bytes(_make_zip({"Positions.csv": positions}))
        out = parse_zip(str(zip_path))
        assert out["experience"][0]["company"] == "Acme"
        assert out["experience"][0]["title"] == "Engineer"
        assert out["experience"][0]["bullets"] == ["Built X", "Shipped Y"]

    def test_parses_education(self, tmp_path):
        zip_path = tmp_path / "d.zip"
        zip_path.write_bytes(_make_zip({
            "Education.csv": _build_csv([{
                "School Name": "MIT", "Degree Name": "BS",
                "Start Date": "2020", "End Date": "2024",
            }]),
        }))
        out = parse_zip(str(zip_path))
        assert out["education"][0]["school"] == "MIT"
        assert out["education"][0]["degree"] == "BS"

    def test_skills_dedup_case_insensitive(self, tmp_path):
        zip_path = tmp_path / "d.zip"
        zip_path.write_bytes(_make_zip({
            "Skills.csv": _build_csv([
                {"Name": "Python"}, {"Name": "python"}, {"Name": "Go"},
            ]),
        }))
        out = parse_zip(str(zip_path))
        # Order preserved, dedupe by lowercase
        assert out["skills"] == ["Python", "Go"]

    def test_skills_fallback_to_endorsements(self, tmp_path):
        zip_path = tmp_path / "d.zip"
        zip_path.write_bytes(_make_zip({
            "Endorsement_Received_Info.csv": _build_csv([
                {"Skill Name": "Rust"},
            ]),
        }))
        out = parse_zip(str(zip_path))
        assert out["skills"] == ["Rust"]

    def test_email_and_phone_pick_primary(self, tmp_path):
        zip_path = tmp_path / "d.zip"
        zip_path.write_bytes(_make_zip({
            "Email Addresses.csv": _build_csv([
                {"Email Address": "alt@x.com", "Primary": "No"},
                {"Email Address": "main@x.com", "Primary": "Yes"},
            ]),
            "PhoneNumbers.csv": _build_csv([
                {"Number": "555-0100", "Confirmed": "Yes"},
            ]),
        }))
        out = parse_zip(str(zip_path))
        assert out["general_info"]["email"] == "main@x.com"
        assert out["general_info"]["phone"] == "555-0100"


class TestSummarize:
    def test_includes_counts(self):
        out = summarize({
            "experience": [{}, {}],
            "projects": [],
            "education": [{}],
            "awards": [],
            "skills": [{}, {}, {}],
            "general_info": {"first_name": "A"},
        })
        assert "2 experience" in out
        assert "3 skills" in out
        assert "+ identity" in out
