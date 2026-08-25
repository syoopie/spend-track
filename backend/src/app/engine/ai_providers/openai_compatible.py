"""Generic adapter for anything speaking the OpenAI chat-completions shape.

Covers OpenAI itself (including Codex-family models - there's no separate
"Codex provider", it's just this adapter pointed at OpenAI with a code
model name), OpenRouter, Groq, together.ai, a self-hosted LiteLLM proxy,
or any other hosted/local server that mimics this API - one adapter for
the whole family rather than one per vendor.
"""

import httpx

from app.engine.ai_providers.base import (
    AiCandidate,
    AiProviderResponseError,
    AiProviderUnavailableError,
    AiSuggestion,
    ProviderHealth,
    cancellable_client,
    parse_suggestions,
)
from app.engine.ai_providers.prompts import build_prompt

HEALTH_TIMEOUT = 5.0
# See ollama.py's identical constant - no timeout on the categorize call
# itself, a real Cancel action replaces it.
CATEGORIZE_TIMEOUT = None


class OpenAiCompatibleProvider:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    def check_health(self) -> ProviderHealth:
        try:
            resp = httpx.get(f"{self.base_url}/models", headers=self._headers(), timeout=HEALTH_TIMEOUT)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            return ProviderHealth(reachable=False, models=[], error=str(exc))
        data = resp.json()
        models = [m.get("id", "") for m in data.get("data", []) if m.get("id")]
        return ProviderHealth(reachable=True, models=models, error=None)

    def categorize(
        self, candidates: list[AiCandidate], categories: list[tuple[str, str]], *, cancel_key: str | None = None
    ) -> list[AiSuggestion]:
        if not candidates:
            return []
        prompt = build_prompt(candidates, categories)
        try:
            with cancellable_client(CATEGORIZE_TIMEOUT, cancel_key) as client:
                resp = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"},
                        # Classification, not creative writing - see ollama.py's identical comment.
                        "temperature": 0,
                    },
                )
            resp.raise_for_status()
        except Exception as exc:
            # Broad on purpose - see ollama.py's identical comment.
            raise AiProviderUnavailableError(f"Could not reach {self.base_url}: {exc}") from exc

        try:
            content = resp.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise AiProviderResponseError(f"Unexpected response shape from {self.base_url}: {exc}") from exc

        return parse_suggestions(content, candidates, categories)
