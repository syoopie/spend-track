import httpx
import pytest

from app.engine.ai_providers import AiCandidate, build_provider
from app.engine.ai_providers.anthropic import AnthropicProvider
from app.engine.ai_providers.base import AiProviderResponseError, AiProviderUnavailableError, parse_suggestions
from app.engine.ai_providers.ollama import OllamaProvider
from app.engine.ai_providers.openai_compatible import OpenAiCompatibleProvider

CATEGORIES = [("Food & Drink", "outflow"), ("Shopping", "outflow"), ("Salary", "inflow")]

CANDIDATES = [
    AiCandidate(index=0, raw_description="SHENG SIONG SUPERMARKET", amount=-12.5, direction="outflow"),
    AiCandidate(index=1, raw_description="RANDOM PAYEE 12345", amount=2000.0, direction="inflow"),
]


class _FakeResponse:
    def __init__(self, status_code=200, json_body=None):
        self.status_code = status_code
        self._json_body = json_body or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=None, response=self)

    def json(self):
        return self._json_body


# --- shared parse_suggestions ------------------------------------------------


def test_parse_suggestions_accepts_bare_array():
    raw = '[{"index": 0, "category": "Food & Drink", "display_label": "Sheng Siong", "rule_pattern": "SHENG SIONG"}]'
    result = parse_suggestions(raw, CANDIDATES, CATEGORIES)
    assert len(result) == 1
    assert result[0].category == "Food & Drink"
    assert result[0].display_label == "Sheng Siong"
    assert result[0].rule_pattern == "SHENG SIONG"


def test_parse_suggestions_accepts_object_wrapped_array():
    raw = '{"results": [{"index": 0, "category": "Food & Drink", "display_label": "Sheng Siong", "rule_pattern": null}]}'
    result = parse_suggestions(raw, CANDIDATES, CATEGORIES)
    assert len(result) == 1
    assert result[0].rule_pattern is None


def test_parse_suggestions_strips_markdown_fence():
    raw = '```json\n[{"index": 0, "category": "Food & Drink", "display_label": "Sheng Siong", "rule_pattern": null}]\n```'
    result = parse_suggestions(raw, CANDIDATES, CATEGORIES)
    assert len(result) == 1


def test_parse_suggestions_raises_on_malformed_json():
    with pytest.raises(AiProviderResponseError):
        parse_suggestions("not json at all", CANDIDATES, CATEGORIES)


def test_parse_suggestions_drops_unknown_category():
    raw = '[{"index": 0, "category": "Made Up Category", "display_label": "X", "rule_pattern": null}]'
    assert parse_suggestions(raw, CANDIDATES, CATEGORIES) == []


def test_parse_suggestions_drops_direction_mismatch():
    # "Salary" is inflow-only; candidate 0 is an outflow transaction.
    raw = '[{"index": 0, "category": "Salary", "display_label": "X", "rule_pattern": null}]'
    assert parse_suggestions(raw, CANDIDATES, CATEGORIES) == []


def test_parse_suggestions_drops_unknown_index():
    raw = '[{"index": 999, "category": "Food & Drink", "display_label": "X", "rule_pattern": null}]'
    assert parse_suggestions(raw, CANDIDATES, CATEGORIES) == []


# --- OllamaProvider -----------------------------------------------------------


def test_ollama_check_health_reachable(monkeypatch):
    monkeypatch.setattr(
        httpx, "get", lambda url, timeout: _FakeResponse(json_body={"models": [{"name": "llama3.1"}]})
    )
    health = OllamaProvider("http://localhost:11434", "llama3.1").check_health()
    assert health.reachable is True
    assert health.models == ["llama3.1"]


def test_ollama_check_health_unreachable(monkeypatch):
    def _raise(url, timeout):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "get", _raise)
    health = OllamaProvider("http://localhost:11434", "llama3.1").check_health()
    assert health.reachable is False
    assert health.error is not None


def test_ollama_categorize_happy_path(monkeypatch):
    body = {"message": {"content": '[{"index": 0, "category": "Food & Drink", "display_label": "Sheng Siong", "rule_pattern": "SHENG SIONG"}]'}}
    monkeypatch.setattr(httpx.Client, "post", lambda self, url, **kwargs: _FakeResponse(json_body=body))
    suggestions = OllamaProvider("http://localhost:11434", "llama3.1").categorize(CANDIDATES, CATEGORIES)
    assert len(suggestions) == 1
    assert suggestions[0].category == "Food & Drink"


def test_ollama_categorize_unavailable(monkeypatch):
    def _raise(self, url, **kwargs):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx.Client, "post", _raise)
    with pytest.raises(AiProviderUnavailableError):
        OllamaProvider("http://localhost:11434", "llama3.1").categorize(CANDIDATES, CATEGORIES)


def test_ollama_categorize_empty_candidates_skips_network(monkeypatch):
    def _fail(*a, **k):
        raise AssertionError("should not be called")

    monkeypatch.setattr(httpx.Client, "post", _fail)
    assert OllamaProvider("http://localhost:11434", "llama3.1").categorize([], CATEGORIES) == []


def test_ollama_categorize_registers_and_unregisters_cancel_key(monkeypatch):
    from app.engine.ai_providers import cancellation

    seen: dict[str, bool] = {}

    def fake_post(self, url, **kwargs):
        seen["registered_during_call"] = cancellation._clients.get("batch-123") is self
        return _FakeResponse(json_body={"message": {"content": "[]"}})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    OllamaProvider("http://localhost:11434", "llama3.1").categorize(CANDIDATES, CATEGORIES, cancel_key="batch-123")
    assert seen["registered_during_call"] is True
    assert "batch-123" not in cancellation._clients  # unregistered again once the call finished


# --- OpenAiCompatibleProvider --------------------------------------------------


def test_openai_compatible_check_health(monkeypatch):
    monkeypatch.setattr(
        httpx, "get", lambda url, headers, timeout: _FakeResponse(json_body={"data": [{"id": "gpt-4o-mini"}]})
    )
    health = OpenAiCompatibleProvider("https://api.openai.com/v1", "sk-test", "gpt-4o-mini").check_health()
    assert health.reachable is True
    assert health.models == ["gpt-4o-mini"]


def test_openai_compatible_categorize_happy_path(monkeypatch):
    content = '{"results": [{"index": 1, "category": "Salary", "display_label": "Employer", "rule_pattern": null}]}'
    body = {"choices": [{"message": {"content": content}}]}
    monkeypatch.setattr(httpx.Client, "post", lambda self, url, **kwargs: _FakeResponse(json_body=body))
    suggestions = OpenAiCompatibleProvider("https://api.openai.com/v1", "sk-test", "gpt-4o-mini").categorize(
        CANDIDATES, CATEGORIES
    )
    assert len(suggestions) == 1
    assert suggestions[0].index == 1


# --- AnthropicProvider ----------------------------------------------------------


def test_anthropic_check_health(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda url, headers, json, timeout: _FakeResponse(json_body={}))
    health = AnthropicProvider("sk-ant-test", "claude-sonnet-5").check_health()
    assert health.reachable is True


def test_anthropic_categorize_happy_path(monkeypatch):
    body = {
        "content": [
            {"type": "text", "text": '[{"index": 0, "category": "Shopping", "display_label": "X", "rule_pattern": null}]'}
        ]
    }
    monkeypatch.setattr(httpx.Client, "post", lambda self, url, **kwargs: _FakeResponse(json_body=body))
    suggestions = AnthropicProvider("sk-ant-test", "claude-sonnet-5").categorize(CANDIDATES, CATEGORIES)
    assert len(suggestions) == 1
    assert suggestions[0].category == "Shopping"


# --- cancellation ---------------------------------------------------------------


def test_cancel_closes_registered_client():
    from app.engine.ai_providers import cancellation

    class _FakeClient:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    client = _FakeClient()
    cancellation.register("k", client)
    cancellation.cancel("k")
    assert client.closed is True
    assert "k" not in cancellation._clients


def test_cancel_is_a_no_op_when_nothing_registered():
    from app.engine.ai_providers import cancellation

    cancellation.cancel("nonexistent-key")  # must not raise


# --- build_provider factory -----------------------------------------------------


def test_build_provider_selects_ollama():
    settings = {"ai_provider": "ollama", "ollama_url": "http://x", "ollama_model": "m"}
    assert isinstance(build_provider(settings), OllamaProvider)


def test_build_provider_selects_openai_compatible():
    settings = {
        "ai_provider": "openai_compatible",
        "openai_base_url": "https://x",
        "openai_api_key": "k",
        "openai_model": "m",
    }
    assert isinstance(build_provider(settings), OpenAiCompatibleProvider)


def test_build_provider_selects_anthropic():
    settings = {"ai_provider": "anthropic", "anthropic_api_key": "k", "anthropic_model": "m"}
    assert isinstance(build_provider(settings), AnthropicProvider)
