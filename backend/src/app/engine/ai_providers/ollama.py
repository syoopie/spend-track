"""Local Ollama provider - the default, no API key, nothing leaves the device."""

import httpx

from app.engine.ai_providers.base import (
    AiCandidate,
    AiProviderResponseError,
    AiProviderUnavailableError,
    AiSuggestion,
    ProviderHealth,
    build_prompt,
    cancellable_client,
    parse_suggestions,
)

HEALTH_TIMEOUT = 3.0
CATEGORIZE_TIMEOUT = 90.0


class OllamaProvider:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def check_health(self) -> ProviderHealth:
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=HEALTH_TIMEOUT)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            return ProviderHealth(reachable=False, models=[], error=str(exc))
        data = resp.json()
        models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
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
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "format": "json",
                        "stream": False,
                    },
                )
            resp.raise_for_status()
        except Exception as exc:
            # Broad on purpose: a cancellation-triggered connection teardown
            # (see cancellation.py) doesn't reliably surface as httpx.HTTPError
            # across platforms - anything that isn't a clean response is
            # equally "this call didn't succeed" from the caller's view.
            raise AiProviderUnavailableError(f"Could not reach Ollama at {self.base_url}: {exc}") from exc

        try:
            content = resp.json()["message"]["content"]
        except (KeyError, ValueError) as exc:
            raise AiProviderResponseError(f"Unexpected Ollama response shape: {exc}") from exc

        return parse_suggestions(content, candidates, categories)
