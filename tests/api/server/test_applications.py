import pytest
from fastapi.testclient import TestClient

from api.server import app


pytestmark = pytest.mark.usefixtures("isolated_app_dir")


@pytest.fixture
def client():
    return TestClient(app)


class TestListApplications:
    def test_empty_initially(self, client):
        resp = client.get("/applications")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_entries_with_uuid(self, client):
        from api import data_store
        d = data_store.load()
        d["applications"] = [
            {"uuid": "u1", "company": "Acme", "role": "SWE", "links": ["http://a"]},
        ]
        data_store.save(d)
        resp = client.get("/applications")
        assert resp.json() == [{
            "uuid": "u1",
            "company": "Acme",
            "role": "SWE",
            "links": ["http://a"],
            "resume_pdf": "",
        }]


class TestCreateApplication:
    def test_creates_and_persists(self, client):
        resp = client.post("/applications", json={
            "company": "Acme", "role": "SWE",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["count"] == 1
        assert isinstance(body["uuid"], str) and body["uuid"]

        listing = client.get("/applications").json()
        assert listing[0]["company"] == "Acme"
        assert listing[0]["uuid"] == body["uuid"]

    def test_bulk_creates_multiple(self, client):
        resp = client.post("/applications/bulk", json={
            "entries": [
                {"company": "A"}, {"company": "B"}, {"company": "C"},
            ],
        })
        body = resp.json()
        assert body["ok"] is True
        assert body["added"] == 3
        assert body["count"] == 3
        assert isinstance(body["uuids"], list) and len(body["uuids"]) == 3


class TestAttachLink:
    def _create(self, client, **fields):
        resp = client.post("/applications", json=fields)
        return resp.json()["uuid"]

    def test_appends_unique_link(self, client):
        uuid = self._create(client, company="Acme")
        resp = client.post(f"/applications/by-uuid/{uuid}/links", json={"url": "http://a"})
        assert resp.json() == {"ok": True, "links": ["http://a"]}

    def test_deduplicates(self, client):
        uuid = self._create(client, company="Acme", links=["http://a"])
        resp = client.post(f"/applications/by-uuid/{uuid}/links", json={"url": "http://a"})
        assert resp.json()["links"] == ["http://a"]

    def test_empty_url_rejected(self, client):
        uuid = self._create(client, company="Acme")
        resp = client.post(f"/applications/by-uuid/{uuid}/links", json={"url": "   "})
        assert resp.status_code == 400

    def test_unknown_uuid_404(self, client):
        resp = client.post("/applications/by-uuid/does-not-exist/links", json={"url": "http://a"})
        assert resp.status_code == 404
