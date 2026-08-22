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
