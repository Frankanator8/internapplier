from __future__ import annotations

import pytest

from api import resume_builder_store


pytestmark = pytest.mark.usefixtures("isolated_app_dir")


def test_load_empty_when_no_file():
    draft = resume_builder_store.load_draft()
    assert draft["company"] == ""
    assert draft["job_title"] == ""
    assert draft["sections"] == []


def test_malformed_sections_become_empty_list():
    from api import constants
    from api.json_store import save_json

    save_json(constants.RESUME_BUILDER_DRAFT_FILE, {"company": "X", "sections": "nope"})
    draft = resume_builder_store.load_draft()
    assert draft["company"] == "X"
    assert draft["sections"] == []


def test_save_then_load_round_trip():
    payload = {
        "company": "Acme",
        "job_title": "Intern",
        "sections": [{
            "id": "sec1",
            "title": "Education",
            "items": [{"id": "i1", "kind": "education", "data": {"school": "MIT"}}],
        }],
    }
    resume_builder_store.save_draft(payload)
    loaded = resume_builder_store.load_draft()
    assert loaded["company"] == "Acme"
    assert loaded["job_title"] == "Intern"
    assert loaded["sections"][0]["title"] == "Education"
    assert loaded["sections"][0]["items"][0]["data"]["school"] == "MIT"
