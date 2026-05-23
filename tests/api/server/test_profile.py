import pytest
from fastapi.testclient import TestClient

from api.server import app


pytestmark = pytest.mark.usefixtures("isolated_app_dir")


@pytest.fixture
def client():
    return TestClient(app)


class TestProfileEndpoints:
    def test_profile_returns_empty_initially(self, client):
        resp = client.get("/profile")
        assert resp.status_code == 200
        assert resp.json()["experience"] == []

    def test_general_info_subset(self, client):
        from api import data_store
        d = data_store.load()
        d["general_info"] = {"first_name": "Ada", "email": "a@b.com"}
        data_store.save(d)
        resp = client.get("/profile/general_info")
        assert resp.json() == {"first_name": "Ada", "email": "a@b.com"}


class TestStatuses:
    def test_returns_options_and_default(self, client):
        resp = client.get("/statuses")
        body = resp.json()
        assert "Added" in body["statuses"]
        assert body["default"]


class TestAutofillFields:
    def test_returns_all_fields_including_blanks(self, client):
        from api import data_store
        d = data_store.load()
        d["general_info"] = {"first_name": "Ada"}
        data_store.save(d)
        resp = client.get("/autofill/fields")
        body = resp.json()
        assert body["first_name"] == "Ada"
        assert body["last_name"] == ""  # default blank


class TestAnswerQuestion:
    def test_streams_provider_chunks_into_answer(self, client, mocker, fake_api_key):
        from api import data_store
        d = data_store.load()
        d["applications"] = [
            {"uuid": "abc123", "company": "Acme", "description": "JD here"},
        ]
        data_store.save(d)

        fake_provider = mocker.MagicMock()
        fake_provider.answer_question_stream.return_value = iter(
            ["Hello ", "world"]
        )
        mocker.patch("api.server.profile.get_provider", return_value=fake_provider)

        resp = client.post("/answer/question", json={
            "question": "Why?", "application_uuid": "abc123",
        })
        assert resp.json() == {"answer": "Hello world"}

        # Ensure provider received company + JD from app uuid
        call_kwargs = fake_provider.answer_question_stream.call_args.kwargs
        assert call_kwargs["company_name"] == "Acme"
        assert call_kwargs["job_description"] == "JD here"
        assert call_kwargs["question"] == "Why?"


class TestTheme:
    def test_theme_returns_preference(self, client):
        resp = client.get("/theme")
        body = resp.json()
        assert body["preference"] in ("system", "light", "dark")
