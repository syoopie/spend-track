"""The prompt(s) sent to an AI categorization provider.

Every adapter (ollama.py/openai_compatible.py/anthropic.py) funnels its
categorize() call through build_prompt() below rather than building its own
text, so there is exactly one place to read or tune when the model's
picks - category choice, label cleanliness, rule_pattern quality, or the
abstain-on-no-payee behavior - need adjusting. Keeping this split out of
base.py (which stays the shared types + parse_suggestions()) means prompt
wording changes never touch the parsing/validation logic, and vice versa.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.engine.ai_providers.base import AiCandidate


def build_prompt(candidates: list["AiCandidate"], categories: list[tuple[str, str]]) -> str:
    category_lines = "\n".join(f'- "{name}" ({direction})' for name, direction in categories)
    candidate_lines = "\n".join(
        f'{{"index": {json.dumps(c.index)}, "description": {json.dumps(c.raw_description)}, '
        f'"amount": {c.amount}, "direction": "{c.direction}"}}'
        for c in candidates
    )
    return (
        "You are categorizing personal bank transactions. For each transaction below, pick the single best "
        "matching category from the allowed list - you MUST only use a category whose direction matches the "
        "transaction's own direction. Prefer the most specific category that genuinely applies over a broader, "
        "generic one - a general 'Shopping'-style category is a catch-all for retail purchases that don't fit "
        "anywhere else, so don't reach for it when a more specific category already covers the merchant's kind "
        "of business: a cinema, streaming service, or game store belongs under an entertainment category, not "
        "shopping; a furniture, appliance, or household-goods store belongs under a home category, not shopping; "
        "a sporting-goods or fitness merchant belongs under a sports/hobbies category, not shopping. Only fall "
        "back to the generic retail category once you've confirmed no more specific one actually fits.\n\n"
        "Also provide a short, clean, human-readable display label. Whenever an identifiable merchant, company, "
        "or person's name is present in the raw description, the label MUST be (or contain) that actual name - "
        "never substitute it with a generic phrase derived from the category or transaction type (e.g. a taxi "
        "company's own name, not 'Taxi Ride'; an employer's actual name, not just 'Salary Payment'). Raw bank "
        "descriptions are full of noise that "
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
