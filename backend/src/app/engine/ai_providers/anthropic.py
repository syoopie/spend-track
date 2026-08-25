"""Anthropic (Claude) provider - the Messages API shape differs enough from
OpenAI's chat-completions shape (different auth headers, no bare
response_format flag, content comes back as a list of blocks) to warrant
its own adapter rather than folding into openai_compatible.py.

There's no universal free "list available models" probe on this API, so
check_health() issues one minimal real request instead and treats a 200 as
reachable - a deliberate, documented trade-off (negligible token usage),
and it only ever runs on an explicit user action (Settings page mount /
"Recheck" button), never inside an automatic/background retry loop.
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

API_VERSION = "2023-06-01"
HEALTH_TIMEOUT = 8.0
# See ollama.py's identical constant - no timeout on the categorize call
# itself, a real Cancel action replaces it.
CATEGORIZE_TIMEOUT = None


class AnthropicProvider:
    def __init__(self, api_key: str, model: str, base_url: str = "https://api.anthropic.com"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def _headers(self) -> dict:
        return {"x-api-key": self.api_key, "anthropic-version": API_VERSION, "content-type": "application/json"}

    def check_health(self) -> ProviderHealth:
        try:
            resp = httpx.post(
                f"{self.base_url}/v1/messages",
                headers=self._headers(),
                json={"model": self.model, "max_tokens": 1, "messages": [{"role": "user", "content": "ping"}]},
                timeout=HEALTH_TIMEOUT,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            return ProviderHealth(reachable=False, models=[], error=str(exc))
        return ProviderHealth(reachable=True, models=[], error=None)

    def categorize(
        self, candidates: list[AiCandidate], categories: list[tuple[str, str]], *, cancel_key: str | None = None
    ) -> list[AiSuggestion]:
        if not candidates:
            return []
        prompt = build_prompt(candidates, categories)
        try:
            with cancellable_client(CATEGORIZE_TIMEOUT, cancel_key) as client:
                resp = client.post(
                    f"{self.base_url}/v1/messages",
                    headers=self._headers(),
                    json={
                        "model": self.model,
                        "max_tokens": 4096,
                        "messages": [{"role": "user", "content": prompt}],
                        # Classification, not creative writing - see ollama.py's identical comment.
                        "temperature": 0,
                    },
                )
            resp.raise_for_status()
        except Exception as exc:
            # Broad on purpose - see ollama.py's identical comment.
            raise AiProviderUnavailableError(f"Could not reach Anthropic at {self.base_url}: {exc}") from exc

        try:
            content = "".join(block["text"] for block in resp.json()["content"] if block.get("type") == "text")
        except (KeyError, ValueError) as exc:
            raise AiProviderResponseError(f"Unexpected Anthropic response shape: {exc}") from exc

        return parse_suggestions(content, candidates, categories)
