"""Tests for the shared importer merge rules."""
from __future__ import annotations

from api import data_store
from api.profile_merge import apply_to_store, merge_profile


def _store(**overrides) -> dict:
    base = {
        "general_info": {}, "experience": [], "projects": [], "education": [],
        "awards": [], "skills": [], "hobbies": [],
    }
    base.update(overrides)
    return base


class TestMergeProfile:
    def test_append_extends_lists_and_keeps_existing_entries(self):
        store = _store(experience=[{"company": "Old"}])
        out = merge_profile(store, {"experience": [{"company": "New"}]}, "append")
        assert [e["company"] for e in out["experience"]] == ["Old", "New"]

    def test_replace_swaps_lists(self):
        store = _store(experience=[{"company": "Old"}])
        out = merge_profile(store, {"experience": [{"company": "New"}]}, "replace")
        assert [e["company"] for e in out["experience"]] == ["New"]

    def test_replace_leaves_sections_the_importer_never_emits(self):
        """The LinkedIn export has no concept of hobbies — choosing 'replace'
        for what it does know must not wipe what it doesn't."""
        store = _store(hobbies=["chess"], experience=[{"company": "Old"}])
        out = merge_profile(store, {"experience": []}, "replace")
        assert out["hobbies"] == ["chess"]

    def test_general_info_is_overlaid_not_cleared_on_replace(self):
        """Replace means 'replace the sections I found', not 'forget the phone
        number this resume happened to omit'."""
        store = _store(general_info={"phone": "555", "email": "old@x.com"})
        out = merge_profile(store, {"general_info": {"email": "new@x.com"}}, "replace")
        assert out["general_info"] == {"phone": "555", "email": "new@x.com"}

    def test_append_only_fills_blank_general_info_fields(self):
        store = _store(general_info={"email": "mine@x.com"})
        out = merge_profile(
            store, {"general_info": {"email": "theirs@x.com", "phone": "555"}}, "append"
        )
        assert out["general_info"] == {"email": "mine@x.com", "phone": "555"}

    def test_append_dedupes_flat_sections_case_insensitively(self):
        store = _store(skills=["Python"], hobbies=["Chess"])
        out = merge_profile(store, {"skills": ["python", "Go"], "hobbies": ["chess"]}, "append")
        assert out["skills"] == ["Python", "Go"]
        assert out["hobbies"] == ["Chess"]

    def test_does_not_mutate_its_arguments(self):
        """Callers reuse the imported dict for the summary line afterwards."""
        store = _store(experience=[{"company": "Old"}], skills=["Python"])
        data = {"experience": [{"company": "New"}], "skills": ["Go"]}
        merge_profile(store, data, "append")
        assert store["experience"] == [{"company": "Old"}]
        assert store["skills"] == ["Python"]
        assert data == {"experience": [{"company": "New"}], "skills": ["Go"]}


class TestApplyToStore:
    def test_round_trips_through_disk(self, isolated_app_dir):
        apply_to_store({"skills": ["Python"], "general_info": {"email": "a@b.c"}})
        data_store.invalidate()
        stored = data_store.load()
        assert stored["skills"] == ["Python"]
        assert stored["general_info"]["email"] == "a@b.c"

    def test_second_append_accumulates(self, isolated_app_dir):
        apply_to_store({"experience": [{"company": "A"}]})
        apply_to_store({"experience": [{"company": "B"}]})
        data_store.invalidate()
        assert [e["company"] for e in data_store.load()["experience"]] == ["A", "B"]
