"""SHA-256 transaction fingerprinting per docs/technical-spec.md §3.

Fingerprint = SHA256(account_id | date | amount | cleaned_description | daily_sequence_index)

daily_sequence_index is the zero-indexed occurrence count of an identical
(date, amount, description) combination within a single statement file,
which disambiguates genuinely repeated same-day/same-amount transactions
(e.g. two identical bus fares) from true duplicates on re-upload.
"""

import hashlib

from app.parsing.base import ParsedTransaction


def clean_description(raw: str) -> str:
    return " ".join(raw.split()).strip().upper()


def compute_daily_sequence_indices(transactions: list[ParsedTransaction]) -> list[int]:
    """Return, in input order, each transaction's zero-indexed occurrence
    count among prior transactions in the same list sharing its
    (date, amount, cleaned_description) key."""
    seen: dict[tuple[str, float, str], int] = {}
    indices = []
    for t in transactions:
        key = (t.transaction_date, t.amount, clean_description(t.raw_description))
        idx = seen.get(key, 0)
        indices.append(idx)
        seen[key] = idx + 1
    return indices


def compute_fingerprint(
    account_id: str,
    transaction_date: str,
    amount: float,
    cleaned_description: str,
    daily_sequence_index: int,
) -> str:
    payload = "|".join(
        [account_id, transaction_date, f"{amount:.2f}", cleaned_description, str(daily_sequence_index)]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
