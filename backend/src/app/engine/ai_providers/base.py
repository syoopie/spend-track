"""Shared types + response-parsing logic for every AI categorization provider.

Deliberately mirrors parsing/uob/'s subpackage shape: one small file per
concrete provider (ollama.py/openai_compatible.py/anthropic.py), all built
on this shared base so adding a fourth provider later is "write an adapter
class", not "reimplement JSON validation a fourth time". The prompt text
itself lives in prompts.py, not here - see that file's docstring.

Every provider funnels its raw model output through parse_suggestions() so
the same validation rules apply everywhere: an unknown index, a category
name outside the given allowed set, or a category whose direction doesn't
match that candidate's own transaction direction are all silently dropped
rather than guessed at - a model hallucinating a category is worse than a
model just not helping with that one row.
"""

import json
import re
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Literal, Protocol

import httpx

from app.engine.ai_providers import cancellation
from app.engine.naming import extract_display_name

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
def cancellable_client(timeout: float | None, cancel_key: str | None) -> Iterator[httpx.Client]:
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


_FENCE_OPEN_RE = re.compile(r"^```[a-zA-Z0-9]*\s*")
_FENCE_CLOSE_RE = re.compile(r"\s*```$")


def _strip_markdown_fence(text: str) -> str:
    """Some models wrap JSON in a ```json ... ``` fence despite instructions
    not to add other text - strip it rather than fail to parse. Regex-based
    (rather than splitting on the first newline) so a single-line fence with
    no newline after the opening tag - e.g. ```json{"results": []}``` -
    still strips cleanly instead of leaving the tag glued to the JSON."""
    text = text.strip()
    if not text.startswith("```"):
        return text
    text = _FENCE_OPEN_RE.sub("", text, count=1)
    text = _FENCE_CLOSE_RE.sub("", text, count=1)
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

        # A model that skips the label entirely still shouldn't surface raw
        # reference codes/masked numbers - fall back through the same
        # noise-stripping used for rule/contact quick-apply defaults
        # elsewhere (see naming.py's docstring) rather than a blind .title().
        display_label = (item.get("display_label") or "").strip() or extract_display_name(
            candidate.raw_description
        ).title()
        rule_pattern = (item.get("rule_pattern") or "").strip() or None

        suggestions.append(
            AiSuggestion(index=index, category=category, display_label=display_label, rule_pattern=rule_pattern)
        )
    return suggestions
