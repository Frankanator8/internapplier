from __future__ import annotations

from app.sections.applier.builder_widgets import default_section_title, palette_groups


def test_palette_includes_building_blocks_when_profile_empty():
    groups = dict(palette_groups({}))
    assert list(groups)[-1] == "Building blocks"
    kinds = {item["kind"] for item in groups["Building blocks"]}
    assert kinds == {"section", "text"}
    assert groups["Experience"] == []
    assert groups["Skills"] == []


def test_palette_labels_profile_entries():
    groups = dict(palette_groups({
        "experience": [{"title": "Intern", "company": "Acme", "category": "other"}],
        "projects": [{"name": "Engine"}],
        "education": [{"school": "MIT", "degree": "B.S."}],
        "awards": [{"title": "Dean's List", "issuer": "MIT"}],
        "skills": ["Python", "Go", "Rust", "C", "Java"],
        "hobbies": ["Chess"],
    }))
    assert groups["Experience"][0]["label"] == "Intern @ Acme"
    assert groups["Projects"][0]["label"] == "Engine"
    assert groups["Education"][0]["label"] == "MIT — B.S."
    assert groups["Awards"][0]["label"] == "Dean's List — MIT"
    assert groups["Skills"][0]["kind"] == "skills"
    assert groups["Skills"][0]["label"].endswith("…")
    assert groups["Hobbies"][0]["data"]["items"] == ["Chess"]


def test_default_section_titles():
    assert default_section_title("experience", {}) == "Relevant Experience"
    assert default_section_title("experience", {"category": "other"}) == "Leadership Experience"
    assert default_section_title("project", {}) == "Projects"
    assert default_section_title("section", {}) == "New Section"
