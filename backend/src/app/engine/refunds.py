"""Refund/reversal pairing reconciliation.

Deviation from the literal SQL in TECHNICAL_SPEC.md §4: that query joins
purely on `t1.amount = -t2.amount`, which would mass-false-positive (e.g.
two unrelated $5 MRT trips on the same account net to nothing but aren't a
refund pair). The spec's own prose says pairing requires "identical merchant
string patterns", and the real UI mockup data confirms it: `Zalora` (outflow)
pairs with `Zalora Refund` (inflow) - not identical strings, but one contains
the other. So a candidate pair must additionally pass a normalized-merchant
containment check.
"""

import re
from typing import Any, Mapping, Sequence

AMOUNT_EPSILON = 0.005
SUFFIX_TOKENS = {"REFUND", "REVERSAL", "REVERSED", "CREDIT", "CR"}


def normalize_merchant(description: str) -> str:
    text = re.sub(r"[^A-Z0-9 ]", " ", description.upper())
    words = [w for w in text.split() if w]
    while words and words[-1] in SUFFIX_TOKENS:
        words.pop()
    return " ".join(words)


def is_merchant_match(desc_a: str, desc_b: str) -> bool:
    a, b = normalize_merchant(desc_a), normalize_merchant(desc_b)
    if not a or not b:
        return False
    return a in b or b in a


def find_refund_pairs(
    transactions: Sequence[Mapping[str, Any]],
    already_paired_ids: frozenset[int] = frozenset(),
) -> list[tuple[int, int]]:
    """transactions: rows for a single account (id, transaction_date, amount,
    raw_description). Returns (original_transaction_id, refund_transaction_id)
    pairs to insert into refund_pairings - excludes ids already paired so
    reconciliation can be safely re-run after each commit."""
    outflows = [t for t in transactions if t["amount"] < 0 and t["id"] not in already_paired_ids]
    inflows = [t for t in transactions if t["amount"] > 0 and t["id"] not in already_paired_ids]

    pairs: list[tuple[int, int]] = []
    used_inflow_ids: set[int] = set()

    for out in sorted(outflows, key=lambda t: t["transaction_date"]):
        candidates = [
            inf
            for inf in inflows
            if inf["id"] not in used_inflow_ids
            and inf["transaction_date"] >= out["transaction_date"]
            and abs(inf["amount"] + out["amount"]) < AMOUNT_EPSILON
            and is_merchant_match(out["raw_description"], inf["raw_description"])
        ]
        if not candidates:
            continue
        best = min(candidates, key=lambda inf: inf["transaction_date"])
        pairs.append((out["id"], best["id"]))
        used_inflow_ids.add(best["id"])

    return pairs
