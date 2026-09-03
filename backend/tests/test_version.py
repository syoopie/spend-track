import pytest
from fastapi.testclient import TestClient

import app.updates as updates
from app.updates import _is_newer


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SG_TRACKER_DB_PATH", str(tmp_path / "test.db"))
    from app.main import app

    # The cache lives for the life of the process, so it outlives a test.
    updates.reset_cache()
    with TestClient(app) as c:
        yield c
    updates.reset_cache()


def test_version_endpoint_shape(client, monkeypatch):
    monkeypatch.setattr(updates, "_fetch_latest", lambda: "0.0.1")
    body = client.get("/api/version").json()
    assert set(body) == {"current", "latest", "update_available", "release_url"}
    assert body["release_url"] == "https://github.com/syoopie/spend-track/releases/latest"
    assert isinstance(body["current"], str)


def test_newer_release_is_reported(client, monkeypatch):
    monkeypatch.setattr(updates, "_fetch_latest", lambda: "999.0.0")
    body = client.get("/api/version").json()
    assert body["latest"] == "999.0.0"
    assert body["update_available"] is True


def test_older_release_is_not_an_update(client, monkeypatch):
    monkeypatch.setattr(updates, "_fetch_latest", lambda: "0.0.1")
    body = client.get("/api/version").json()
    assert body["latest"] == "0.0.1"
    assert body["update_available"] is False


def test_a_failed_check_still_answers(client, monkeypatch):
    monkeypatch.setattr(updates, "_fetch_latest", lambda: None)
    resp = client.get("/api/version")
    assert resp.status_code == 200
    body = resp.json()
    assert body["latest"] is None
    assert body["update_available"] is False


def test_github_is_asked_once_per_process(client, monkeypatch):
    calls = []

    def counted():
        calls.append(1)
        return "999.0.0"

    monkeypatch.setattr(updates, "_fetch_latest", counted)
    client.get("/api/version")
    client.get("/api/version")
    assert len(calls) == 1


def test_is_newer_compares_numerically_not_lexically():
    assert _is_newer("0.2.10", "0.2.9") is True
    assert _is_newer("0.2.2", "0.2.2") is False
    assert _is_newer("garbage", "0.2.2") is False
