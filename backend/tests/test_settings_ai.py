import pytest
from fastapi.testclient import TestClient

from app.engine.ai_providers.base import ProviderHealth


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SG_TRACKER_DB_PATH", str(tmp_path / "test.db"))
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_settings_default_ai_fields(client):
    body = client.get("/api/settings").json()
    assert body["ai_enabled"] is False
    assert body["ai_provider"] == "ollama"
    assert body["ollama_url"] == "http://localhost:11434"
    assert body["openai_api_key_set"] is False
    assert body["anthropic_api_key_set"] is False


def test_patch_ai_settings_persists(client):
    resp = client.patch(
        "/api/ai", json={"ai_enabled": True, "ai_provider": "ollama", "ollama_model": "llama3.1"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ai_enabled"] is True
    assert body["ollama_model"] == "llama3.1"

    refetched = client.get("/api/settings").json()
    assert refetched["ai_enabled"] is True
    assert refetched["ollama_model"] == "llama3.1"


def test_patch_ai_settings_requires_model_when_enabling(client):
    resp = client.patch("/api/ai", json={"ai_enabled": True, "ai_provider": "ollama"})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "AI_PROVIDER_NOT_CONFIGURED"


def test_patch_ai_settings_requires_key_for_openai_compatible(client):
    resp = client.patch(
        "/api/ai",
        json={"ai_enabled": True, "ai_provider": "openai_compatible", "openai_model": "gpt-4o-mini"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "AI_PROVIDER_NOT_CONFIGURED"


def test_patch_ai_settings_redacts_api_key(client):
    resp = client.patch(
        "/api/ai",
        json={
            "ai_enabled": True,
            "ai_provider": "openai_compatible",
            "openai_model": "gpt-4o-mini",
            "openai_api_key": "sk-abcdefgh1234",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "openai_api_key" not in body
    assert body["openai_api_key_set"] is True
    assert body["openai_api_key_last4"] == "1234"


def test_patch_ai_settings_blank_key_does_not_clear_stored_key(client):
    client.patch(
        "/api/ai",
        json={
            "ai_enabled": True,
            "ai_provider": "openai_compatible",
            "openai_model": "gpt-4o-mini",
            "openai_api_key": "sk-abcdefgh1234",
        },
    )
    resp = client.patch("/api/ai", json={"openai_model": "gpt-4o"})
    assert resp.status_code == 200
    assert resp.json()["openai_api_key_set"] is True
    assert resp.json()["openai_api_key_last4"] == "1234"


def test_patch_ai_settings_explicit_clear_removes_key(client):
    client.patch(
        "/api/ai",
        json={
            "ai_enabled": True,
            "ai_provider": "openai_compatible",
            "openai_model": "gpt-4o-mini",
            "openai_api_key": "sk-abcdefgh1234",
        },
    )
    # Clearing the key of the currently-enabled provider is itself rejected
    # by the same AI_PROVIDER_NOT_CONFIGURED validation as never setting one -
    # staying enabled with no key would just fail on the next categorize call.
    still_enabled = client.patch("/api/ai", json={"clear_openai_api_key": True})
    assert still_enabled.status_code == 400
    assert still_enabled.json()["detail"]["code"] == "AI_PROVIDER_NOT_CONFIGURED"

    client.patch("/api/ai", json={"ai_enabled": False})
    resp = client.patch("/api/ai", json={"clear_openai_api_key": True})
    assert resp.status_code == 200
    assert resp.json()["openai_api_key_set"] is False
    assert resp.json()["openai_api_key_last4"] is None


def test_ai_status_reachable(client, monkeypatch):
    monkeypatch.setattr(
        "app.routers.ai_settings.build_provider",
        lambda settings: type("P", (), {"check_health": lambda self: ProviderHealth(True, ["llama3.1"], None)})(),
    )
    resp = client.get("/api/ai/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["reachable"] is True
    assert body["models"] == ["llama3.1"]


def test_ai_status_unreachable(client, monkeypatch):
    monkeypatch.setattr(
        "app.routers.ai_settings.build_provider",
        lambda settings: type("P", (), {"check_health": lambda self: ProviderHealth(False, [], "refused")})(),
    )
    resp = client.get("/api/ai/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["reachable"] is False
    assert body["error"] == "refused"


def test_ai_test_endpoint_checks_draft_without_persisting(client, monkeypatch):
    seen_settings = {}

    def fake_build_provider(settings):
        seen_settings.update(settings)
        return type("P", (), {"check_health": lambda self: ProviderHealth(True, ["gpt-4o-mini"], None)})()

    monkeypatch.setattr("app.routers.ai_settings.build_provider", fake_build_provider)
    resp = client.post(
        "/api/ai/test",
        json={"ai_provider": "openai_compatible", "openai_model": "gpt-4o-mini", "openai_api_key": "sk-abcdefgh1234"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["reachable"] is True
    assert body["models"] == ["gpt-4o-mini"]
    # The draft was checked with the typed key merged in...
    assert seen_settings["openai_api_key"] == "sk-abcdefgh1234"

    # ...but nothing was written to config.json - the saved settings are untouched.
    refetched = client.get("/api/settings").json()
    assert refetched["ai_enabled"] is False
    assert refetched["openai_api_key_set"] is False


def test_ai_test_endpoint_falls_back_to_saved_key_when_draft_key_blank(client, monkeypatch):
    client.patch(
        "/api/ai",
        json={"ai_provider": "openai_compatible", "openai_model": "gpt-4o-mini", "openai_api_key": "sk-savedkey1234"},
    )
    seen_settings = {}

    def fake_build_provider(settings):
        seen_settings.update(settings)
        return type("P", (), {"check_health": lambda self: ProviderHealth(True, [], None)})()

    monkeypatch.setattr("app.routers.ai_settings.build_provider", fake_build_provider)
    resp = client.post("/api/ai/test", json={"ai_provider": "openai_compatible", "openai_model": "gpt-4o-mini"})
    assert resp.status_code == 200
    assert seen_settings["openai_api_key"] == "sk-savedkey1234"


def test_check_path_rejects_relative_path(client):
    resp = client.post("/api/data-lifecycle/check-path", json={"path": "relative/data.db"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    assert "absolute" in body["error"].lower()


def test_check_path_rejects_missing_parent_dir(client, tmp_path):
    missing = tmp_path / "does-not-exist" / "data.db"
    resp = client.post("/api/data-lifecycle/check-path", json={"path": str(missing)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    assert "does not exist" in body["error"].lower()


def test_check_path_accepts_writable_target(client, tmp_path):
    target = tmp_path / "relocated.db"
    resp = client.post("/api/data-lifecycle/check-path", json={"path": str(target)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["free_bytes"] is not None
    assert body["resolved_path"] == str(target.resolve())


def test_check_path_rejects_a_directory(client, tmp_path):
    resp = client.post("/api/data-lifecycle/check-path", json={"path": str(tmp_path)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    assert "directory" in body["error"].lower()
