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
        "transaction's own direction.\n\n"
        "Also provide a short, clean, human-readable display label. Raw bank descriptions are full of noise that "
        "must NOT end up in the label: payment-rail/processing boilerplate (NETS, POS, PAYNOW, GIRO, DEBIT-"
        "CONSUMER, PURCHASE, TRANSFER, INWARD, OTHR, inward/outward markers), transaction reference codes, "
        "terminal/batch IDs, and masked card or account numbers (long digit runs, or patterns like 'xxxxxx1234'). "
        "Never just title-case the raw description and call it the label - strip the noise down to the actual "
        "merchant or person's name first. If a code is glued directly onto a name with no space (e.g. "
        "'HENG LI12306400', where '12306400' is a reference number stuck onto 'LI'), still drop the digit "
        "portion rather than keeping it. Example: raw description "
        '"NETS Debit-Consumer HENG LI12306400 xxxxxx5678" -> label "Heng Li", NOT "Nets Debit-Consumer Heng '
        'Li12306400 Xxxxxx5678". If, after stripping all of that, nothing identifiable remains, use a short '
        'generic label for what the transaction structurally looks like (e.g. "Card Purchase", "Bank Transfer") '
        "instead of falling back to any of the raw noise.\n\n"
        "Also provide a short UPPERCASE substring of the raw description that would reliably match this same "
        "merchant in future transactions - it must be a stable brand/name fragment, never a reference code, "
        "terminal ID, or masked card/account number (those are different on every transaction, so a rule built "
        "from one would never match again). Use null if the description is too generic/one-off for a reliable "
        "rule.\n\n"
        "Some transactions are a generic funds-transfer or bill-payment line with no identifiable payee at all - "
        'e.g. "PAYMT THRU E-BANK/HOMEB/CYBERB", a bare "GIRO", "FAST PAYMENT", "IBG", or "FUNDS TRANSFER" with no '
        "name attached. These are commonly credit card bill payments, loan repayments, or other bill payments - "
        "not a specific purchase - and the description alone gives no way to tell which. Guessing a spending "
        "category for one of these risks being flatly wrong, and if it actually was a credit card bill payment "
        "and the user also tracks that card's own statement here, confidently labeling it as everyday spending "
        "would double-count money already counted on the card statement. For a transaction like this, where "
        "nothing about the payee or purpose can be determined from the description, respond with "
        '"category": null instead of guessing - leaving it uncategorized for the user to resolve by hand is '
        "better than a wrong guess.\n\n"
        f"Allowed categories (name, direction):\n{category_lines}\n\n"
        f"Transactions:\n[{candidate_lines}]\n\n"
        'Respond with ONLY a JSON object of the exact shape {"results": [...]}, no other text - "results" must be '
        "an array with one object per transaction, each shaped exactly like: "
        '{"index": <same index value given above>, "category": "<one of the allowed category names, or null if '
        'you genuinely cannot tell what this transaction was for>", '
        '"display_label": "<clean label>", "rule_pattern": "<UPPERCASE substring or null>"}'
    )


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
