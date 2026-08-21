"""Shared types + prompt/parsing logic for every AI categorization provider.

Deliberately mirrors parsing/uob/'s subpackage shape: one small file per
concrete provider (ollama.py/openai_compatible.py/anthropic.py), all built
on this shared base so adding a fourth provider later is "write an adapter
class", not "reimplement prompt building and JSON validation a fourth time".

Every provider funnels its raw model output through parse_suggestions() so
the same validation rules apply everywhere: an unknown index, a category
name outside the given allowed set, or a category whose direction doesn't
match that candidate's own transaction direction are all silently dropped
rather than guessed at - a model hallucinating a category is worse than a
model just not helping with that one row.
"""

import json
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Literal, Protocol

import httpx

from app.engine.ai_providers import cancellation

Direction = Literal["inflow", "outflow"]


@dataclass
class AiCandidate:
    index: int | str  # opaque correlation key - staging uses a row's positional index, recategorize uses a transaction id
    raw_description: str
    amount: float
    direction: Direction


@dataclass
class AiSuggestion:
    index: int | str
    category: str
    display_label: str
    rule_pattern: str | None


@dataclass
class ProviderHealth:
    reachable: bool
    models: list[str]
    error: str | None


class AiProviderUnavailableError(Exception):
    """The provider couldn't be reached at all (network/connection/HTTP error)."""


class AiProviderResponseError(Exception):
    """The provider responded, but its content couldn't be parsed as suggestions."""


class AiProvider(Protocol):
    def check_health(self) -> ProviderHealth: ...

    def categorize(
        self, candidates: list[AiCandidate], categories: list[tuple[str, str]], *, cancel_key: str | None = None
    ) -> list[AiSuggestion]: ...


@contextmanager
def cancellable_client(timeout: float, cancel_key: str | None) -> Iterator[httpx.Client]:
    """A Client every provider's categorize() POST goes through instead of a
    bare module-level httpx.post - registered under cancel_key (typically
    the staging batch id) for the duration of the call so
    ai_providers.cancellation.cancel(key) can close it from another thread
    if the user discards the batch before the model responds. See
    cancellation.py's own docstring for what this can and can't guarantee."""
    client = httpx.Client(timeout=timeout)
    if cancel_key:
        cancellation.register(cancel_key, client)
    try:
        yield client
    finally:
        if cancel_key:
            cancellation.unregister(cancel_key)
        client.close()


def build_prompt(candidates: list[AiCandidate], categories: list[tuple[str, str]]) -> str:
    category_lines = "\n".join(f'- "{name}" ({direction})' for name, direction in categories)
    candidate_lines = "\n".join(
        f'{{"index": {json.dumps(c.index)}, "description": {json.dumps(c.raw_description)}, '
        f'"amount": {c.amount}, "direction": "{c.direction}"}}'
        for c in candidates
    )
    return (
        "You are categorizing personal bank transactions. For each transaction below, pick the single best "
        "matching category from the allowed list - you MUST only use a category whose direction matches the "
        "transaction's own direction. Also provide a short, clean, human-readable display label (e.g. a merchant "
        "or person's name, title-cased), and a short UPPERCASE substring of the raw description that would "
        "reliably match this same merchant in future transactions (or null if the description is too generic/"
        "one-off to make a reliable rule from).\n\n"
        f"Allowed categories (name, direction):\n{category_lines}\n\n"
        f"Transactions:\n[{candidate_lines}]\n\n"
        'Respond with ONLY a JSON object of the exact shape {"results": [...]}, no other text - "results" must be '
        "an array with one object per transaction, each shaped exactly like: "
        '{"index": <same index value given above>, "category": "<one of the allowed category names>", '
        '"display_label": "<clean label>", "rule_pattern": "<UPPERCASE substring or null>"}'
    )


def _strip_markdown_fence(text: str) -> str:
    """Some models wrap JSON in a ```json ... ``` fence despite instructions
    not to add other text - strip it rather than fail to parse."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[: -len("```")]
    return text.strip()


def parse_suggestions(
    raw_text: str, candidates: list[AiCandidate], categories: list[tuple[str, str]]
) -> list[AiSuggestion]:
    try:
        parsed = json.loads(_strip_markdown_fence(raw_text))
    except json.JSONDecodeError as exc:
        raise AiProviderResponseError(f"Model response was not valid JSON: {exc}") from exc

    if isinstance(parsed, dict):
        # some models wrap the array in an object (e.g. {"results": [...]})  rather than
        # returning a bare array even when explicitly asked to - accept either shape.
        items = next((v for v in parsed.values() if isinstance(v, list)), None)
        if items is None:
            raise AiProviderResponseError("Model response JSON did not contain an array of suggestions.")
    elif isinstance(parsed, list):
        items = parsed
    else:
        raise AiProviderResponseError("Model response JSON was neither an array nor an object containing one.")

    by_index = {c.index: c for c in candidates}
    direction_by_category = dict(categories)

    suggestions: list[AiSuggestion] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        index = item.get("index")
        candidate = by_index.get(index)
        if candidate is None:
            continue  # unknown/malformed index - drop rather than guess which row it meant

        category = item.get("category")
        if category not in direction_by_category or direction_by_category[category] != candidate.direction:
            continue  # not an allowed category, or wrong direction for this transaction - drop

        display_label = (item.get("display_label") or "").strip() or candidate.raw_description.title()
        rule_pattern = (item.get("rule_pattern") or "").strip() or None

        suggestions.append(
            AiSuggestion(index=index, category=category, display_label=display_label, rule_pattern=rule_pattern)
        )
    return suggestions
