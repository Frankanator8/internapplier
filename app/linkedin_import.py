"""Parse a LinkedIn 'Get a copy of your data' ZIP archive into our resume schema.

The archive lives at LinkedIn → Settings → Data Privacy → Get a copy of your data.
We read these CSVs if present:
    Positions.csv    → experience
    Projects.csv     → projects
    Education.csv    → education
    Honors.csv       → awards
    Skills.csv       → skills
"""
from __future__ import annotations

import csv
import io
import zipfile
from typing import Iterable


def _open_csv(zf: zipfile.ZipFile, *candidates: str) -> list[dict] | None:
    """Return list[dict] rows of the first matching CSV (case-insensitive), or None."""
    names_lower = {n.lower(): n for n in zf.namelist()}
    for cand in candidates:
        # exact match
        if cand.lower() in names_lower:
            real = names_lower[cand.lower()]
            return _read_csv(zf, real)
        # match basename anywhere (LinkedIn nests files in folders sometimes)
        for lower, real in names_lower.items():
            if lower.endswith("/" + cand.lower()) or lower == cand.lower():
                return _read_csv(zf, real)
    return None


def _read_csv(zf: zipfile.ZipFile, name: str) -> list[dict]:
    with zf.open(name) as f:
        text = io.TextIOWrapper(f, encoding="utf-8-sig", newline="")
        reader = csv.DictReader(text)
        return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]


def _get(row: dict, *keys: str) -> str:
    """Return the first non-empty value among the given column names (case-insensitive)."""
    lower_map = {k.lower(): k for k in row.keys()}
    for k in keys:
        real = lower_map.get(k.lower())
        if real and row.get(real, "").strip():
            return row[real].strip()
    return ""


def _bullets_from_description(text: str) -> list[str]:
    """Split a Description field into bullet points by newline or '•'."""
    if not text:
        return []
    # Normalize bullet markers and split
    text = text.replace("•", "\n").replace("\r\n", "\n").replace("\r", "\n")
    chunks = [c.strip(" -•\t") for c in text.split("\n")]
    return [c for c in chunks if c]


def parse_zip(zip_path: str) -> dict:
    """Parse a LinkedIn data export ZIP and return a resume dict."""
    result: dict = {"experience": [], "projects": [], "education": [], "awards": [], "skills": []}

    with zipfile.ZipFile(zip_path, "r") as zf:
        positions = _open_csv(zf, "Positions.csv") or []
        projects = _open_csv(zf, "Projects.csv") or []
        education = _open_csv(zf, "Education.csv") or []
        skills = _open_csv(zf, "Skills.csv") or []
        courses_rows = _open_csv(zf, "Courses.csv") or []
        honors = _open_csv(zf, "Honors.csv", "Awards.csv") or []

    for row in positions:
        result["experience"].append({
            "company": _get(row, "Company Name", "Company"),
            "title": _get(row, "Title", "Position Title"),
            "start": _get(row, "Started On", "Start Date"),
            "end": _get(row, "Finished On", "End Date") or "Present",
            "bullets": _bullets_from_description(_get(row, "Description")),
        })

    for row in projects:
        result["projects"].append({
            "name": _get(row, "Title", "Name", "Project Name"),
            "url": _get(row, "Url", "URL"),
            "start": _get(row, "Started On", "Start Date"),
            "end": _get(row, "Finished On", "End Date"),
            "bullets": _bullets_from_description(_get(row, "Description")),
        })

    for row in education:
        result["education"].append({
            "school": _get(row, "School Name", "School"),
            "degree": _get(row, "Degree Name", "Degree"),
            "start": _get(row, "Start Date", "Started On"),
            "end": _get(row, "End Date", "Finished On"),
            "gpa": "",
            "bullets": _bullets_from_description(
                _get(row, "Notes", "Description", "Activities")
            ),
            "courses": [],
        })

    school_index = {
        ed["school"].lower(): ed for ed in result["education"] if ed["school"]
    }
    for row in courses_rows:
        name = _get(row, "Name", "Course Name", "Title")
        if not name:
            continue
        school = _get(row, "School Name", "School")
        target = school_index.get(school.lower()) if school else None
        if target is None and result["education"]:
            target = result["education"][0]
        if target is not None:
            target["courses"].append({"name": name, "grade": "", "skills": []})

    for row in honors:
        title = _get(row, "Title", "Name", "Honor")
        if not title:
            continue
        result["awards"].append({
            "title": title,
            "issuer": _get(row, "Issuer", "Issued By", "Organization"),
            "date": _get(row, "Issued On", "Date", "Issue Date"),
            "bullets": _bullets_from_description(_get(row, "Description")),
            "skills": [],
        })

    for row in skills:
        name = _get(row, "Name", "Skill")
        if name:
            result["skills"].append(name)

    return result


def summarize(data: dict) -> str:
    """Short human summary of an imported dict — used in the confirmation dialog."""
    return (
        f"{len(data['experience'])} experience · "
        f"{len(data['projects'])} projects · "
        f"{len(data['education'])} education · "
        f"{len(data.get('awards', []))} awards · "
        f"{len(data['skills'])} skills"
    )
