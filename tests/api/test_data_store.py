import pytest

from api import data_store


pytestmark = pytest.mark.usefixtures("isolated_app_dir")


class TestLoadSave:
    def test_load_empty_when_no_file(self):
        d = data_store.load()
        assert d["general_info"] == {}
        assert d["experience"] == []
        assert d["applications"] == []

    def test_save_then_load_round_trip(self):
        d = data_store.load()
        d["experience"].append({"company": "Acme"})
        data_store.save(d)
        data_store.invalidate()
        d2 = data_store.load()
        assert d2["experience"] == [{"company": "Acme"}]

    def test_empty_returns_fresh_lists(self):
        d1 = data_store._empty_data()
        d2 = data_store._empty_data()
        d1["experience"].append({"x": 1})
        # Verify aliasing did not leak
        assert d2["experience"] == []


class TestMigrateApplicationLinks:
    def test_converts_legacy_link_to_links(self):
        data = {"applications": [{"company": "X", "link": "http://a"}]}
        assert data_store._migrate_application_links(data) is True
        assert data["applications"][0]["links"] == ["http://a"]
        assert "link" not in data["applications"][0]

    def test_empty_link_becomes_empty_list(self):
        data = {"applications": [{"company": "X", "link": ""}]}
        data_store._migrate_application_links(data)
        assert data["applications"][0]["links"] == []

    def test_skips_non_list(self):
        assert data_store._migrate_application_links({"applications": "bad"}) is False

    def test_idempotent_when_links_present(self):
        data = {"applications": [{"links": ["http://a"]}]}
        # Already migrated; no change
        assert data_store._migrate_application_links(data) is False


class TestMigrateResearchCache:
    def test_converts_legacy_research_to_cache(self):
        data = {
            "research": {
                "company_name": "Acme",
                "url": "https://acme",
                "result": {"summary": "ok"},
            },
        }
        assert data_store._migrate_research_cache(data) is True
        assert "Acme" in data["research_cache"]
        assert "research" not in data

    def test_drops_legacy_research_when_cache_already_has_data(self):
        data = {
            "research_cache": {"Acme": {"result": {"summary": "ok"}}},
            "research": {"company_name": "x", "result": {}},
        }
        assert data_store._migrate_research_cache(data) is True
        assert "research" not in data


class TestInterviewTemplate:
    def test_returns_defaults_when_no_file(self):
        items = data_store.load_interview_template()
        assert any(it.get("question") for it in items)

    def test_round_trip(self):
        data_store.save_interview_template([{"question": "Q", "answer": "A"}])
        assert data_store.load_interview_template() == [{"question": "Q", "answer": "A"}]


class TestInterviewFeedback:
    def test_empty_when_no_file(self):
        assert data_store.load_interview_feedback() == []

    def test_round_trip(self):
        data_store.save_interview_feedback([{"id": 1}])
        assert data_store.load_interview_feedback() == [{"id": 1}]

    def test_append(self):
        data_store.append_interview_feedback({"id": 1})
        data_store.append_interview_feedback({"id": 2})
        out = data_store.load_interview_feedback()
        assert [s["id"] for s in out] == [1, 2]

    def test_load_handles_legacy_list_format(self):
        # Some old format may have been a bare list
        path = data_store.INTERVIEW_FEEDBACK_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('[{"id": 1}]')
        assert data_store.load_interview_feedback() == [{"id": 1}]
