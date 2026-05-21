"""Parse a LinkedIn 'Get a copy of your data' ZIP archive into our resume schema.

The archive lives at LinkedIn → Settings → Data Privacy → Get a copy of your data.
We read these CSVs if present:
    Profile.csv             → general_info (name, address, birth date, websites)
    Email Addresses.csv     → general_info.email
    PhoneNumbers.csv        → general_info.phone
    Positions.csv           → experience
    Projects.csv            → projects
    Education.csv           → education
    Honors.csv              → awards
    Skills.csv              → skills
    Endorsement_*_Info.csv  → skills (fallback when Skills.csv is missing)
"""
from __future__ import annotations

import csv
import io
import re
import zipfile


def _open_csv(zf: zipfile.ZipFile, *candidates: str) -> list[dict] | None:
    """Return list[dict] rows of the first matching CSV (case-insensitive), or None."""
    names_lower = {n.lower(): n for n in zf.namelist()}
    for cand in candidates:
        if cand.lower() in names_lower:
            return _read_csv(zf, names_lower[cand.lower()])
        for lower, real in names_lower.items():
            if lower.endswith("/" + cand.lower()):
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
    text = text.replace("•", "\n").replace("\r\n", "\n").replace("\r", "\n")
    chunks = [c.strip(" -•\t") for c in text.split("\n")]
    return [c for c in chunks if c]


def _pick_primary(rows: list[dict], value_keys: tuple[str, ...]) -> str:
    """Pick the 'Primary == Yes' row first, then 'Confirmed == Yes', then the first non-empty."""
    if not rows:
        return ""
    for flag in ("Primary", "Confirmed"):
        for row in rows:
            if _get(row, flag).lower() == "yes":
                v = _get(row, *value_keys)
                if v:
                    return v
    for row in rows:
        v = _get(row, *value_keys)
        if v:
            return v
    return ""


_URL_RE = re.compile(r"https?://[^\s,;\]\[]+")


def _extract_websites(blob: str) -> tuple[str, str]:
    """Return (website, github) by scanning a LinkedIn Websites blob for URLs."""
    if not blob:
        return "", ""
    urls = _URL_RE.findall(blob)
    website = ""
    github = ""
    for u in urls:
        if "github.com" in u.lower() and not github:
            github = u
        elif not website:
            website = u
    return website, github


def _parse_profile(profile_rows: list[dict]) -> dict:
    """Parse Profile.csv (single row) into a partial general_info dict."""
    if not profile_rows:
        return {}
    row = profile_rows[0]
    info: dict[str, str] = {}

    first = _get(row, "First Name", "Given Name")
    last = _get(row, "Last Name", "Family Name", "Surname")
    if first:
        info["first_name"] = first
    if last:
        info["last_name"] = last

    address = _get(row, "Address")
    if address:
        info["address1"] = address

    zip_code = _get(row, "Zip Code", "Postal Code")
    if zip_code:
        info["postal_code"] = zip_code

    # Only split Geo Location if Address didn't already provide city/state.
    if not address:
        geo = _get(row, "Geo Location", "Location")
        if geo:
            parts = [p.strip() for p in geo.split(",") if p.strip()]
            if len(parts) >= 1:
                info["city"] = parts[0]
            if len(parts) >= 2:
                info["state"] = parts[1]
            if len(parts) >= 3:
                info["country"] = parts[2]

    birth = _get(row, "Birth Date", "Birthday")
    if birth:
        info["date_of_birth"] = birth

    websites = _get(row, "Websites", "Website")
    if websites:
        website, github = _extract_websites(websites)
        if website:
            info["website"] = website
        if github:
            info["github"] = github

    return info


def parse_zip(zip_path: str) -> dict:
    """Parse a LinkedIn data export ZIP and return a resume dict."""
    result: dict = {
        "general_info": {},
        "experience": [],
        "projects": [],
        "education": [],
        "awards": [],
        "skills": [],
    }

    with zipfile.ZipFile(zip_path, "r") as zf:
        profile = _open_csv(zf, "Profile.csv") or []
        emails = _open_csv(zf, "Email Addresses.csv", "EmailAddresses.csv", "Emails.csv") or []
        phones = _open_csv(zf, "PhoneNumbers.csv", "Phone Numbers.csv", "Phones.csv") or []
        positions = _open_csv(zf, "Positions.csv") or []
        projects = _open_csv(zf, "Projects.csv") or []
        education = _open_csv(zf, "Education.csv") or []
        skills = _open_csv(
            zf, "Skills.csv", "Skill.csv", "MemberSkills.csv", "Member_Skills.csv"
        ) or []
        courses_rows = _open_csv(zf, "Courses.csv") or []
        honors = _open_csv(zf, "Honors.csv", "Awards.csv") or []
        endorsements_recv = _open_csv(
            zf, "Endorsement_Received_Info.csv", "Endorsements_Received_Info.csv"
        ) or []
        endorsements_giv = _open_csv(
            zf, "Endorsement_Given_Info.csv", "Endorsements_Given_Info.csv"
        ) or []

    # ── general_info ────────────────────────────────────────────────────
    gi = _parse_profile(profile)
    email = _pick_primary(emails, ("Email Address", "Email"))
    if email:
        gi["email"] = email
    phone = _pick_primary(phones, ("Number", "Phone Number", "Phone"))
    if phone:
        gi["phone"] = phone
    result["general_info"] = gi

    # ── experience ──────────────────────────────────────────────────────
    for row in positions:
        result["experience"].append({
            "company": _get(row, "Company Name", "Company"),
            "title": _get(row, "Title", "Position Title"),
            "start": _get(row, "Started On", "Start Date", "Start Year"),
            "end": _get(row, "Finished On", "End Date", "End Year") or "Present",
            "bullets": _bullets_from_description(_get(row, "Description")),
        })

    # ── projects ────────────────────────────────────────────────────────
    for row in projects:
        result["projects"].append({
            "name": _get(row, "Title", "Name", "Project Name"),
            "url": _get(row, "Url", "URL"),
            "start": _get(row, "Started On", "Start Date", "Start Year"),
            "end": _get(row, "Finished On", "End Date", "End Year"),
            "bullets": _bullets_from_description(_get(row, "Description")),
        })

    # ── education ───────────────────────────────────────────────────────
    for row in education:
        result["education"].append({
            "school": _get(row, "School Name", "School"),
            "degree": _get(row, "Degree Name", "Degree"),
            "start": _get(row, "Start Date", "Started On", "Start Year"),
            "end": _get(row, "End Date", "Finished On", "End Year"),
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

    # ── awards ──────────────────────────────────────────────────────────
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

    # ── skills (with endorsement fallback) ──────────────────────────────
    skill_names: list[str] = []
    for row in skills:
        name = _get(row, "Name", "Skill", "Skill Name", "Skills")
        if name:
            skill_names.append(name)

    if not skill_names:
        for row in endorsements_recv + endorsements_giv:
            name = _get(row, "Skill Name", "Skill", "Name")
            if name:
                skill_names.append(name)

    seen: set[str] = set()
    for name in skill_names:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        result["skills"].append(name)

    return result


def summarize(data: dict) -> str:
    """Short human summary of an imported dict — used in the confirmation dialog."""
    parts = [
        f"{len(data['experience'])} experience",
        f"{len(data['projects'])} projects",
        f"{len(data['education'])} education",
        f"{len(data.get('awards', []))} awards",
        f"{len(data['skills'])} skills",
    ]
    summary = " · ".join(parts)
    if data.get("general_info"):
        summary += " + identity"
    return summary
