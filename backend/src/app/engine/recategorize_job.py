"""In-memory pending batch for a recategorize run - deliberately mirrors
engine/staging_store.py's StagingStore/StagingBatch/StagingRow shape and
contract almost exactly (create/get/get_by_id/update_row/delete, the same
"only one pending batch at a time" rule, the same process-wide-singleton
"single local user" caveat) because recategorize is meant to behave
identically to an upload from the app's perspective: nothing is written to
the transactions table until the batch is explicitly committed via
routers/transactions.py::commit_recategorize_batch, and discarding it (or
letting a background AI pass be cancelled - see ai_providers/cancellation.py)
leaves the DB completely untouched.
"""

import uuid
from dataclasses import dataclass, field


@dataclass
class RecategorizeRow:
    transaction_id: int
    account_number_masked: str
    transaction_date: str
    raw_description: str
    matched_label: str | None
    amount: float
    category: str
    subcategory: str | None
    contact_id: int | None
    is_excluded: bool
    exclusion_reason: str | None
    needs_review: bool
    # See staging_store.py::StagingRow's identical field - permanent, set
    # once at row creation, never touched by the update endpoint.
    is_paynow: bool = False
    # See staging_store.py::StagingRow's identical field - needed by
    # engine/rule_rerun.py to re-call categorize() correctly.
    is_card_account: bool = False
    # See staging_store.py::StagingRow's identical fields for why these
    # persist forever instead of being cleared on accept/reject.
    ai_suggested: bool = False
    ai_category: str | None = None
    ai_label: str | None = None
    ai_rule_pattern: str | None = None
    # See staging_store.py::StagingRow's identical field.
    manually_edited: bool = False


@dataclass
class RecategorizeBatch:
    date_from: str
    date_to: str
    account_id: str | None
    scanned: int
    changed: int
    rows: list[RecategorizeRow] = field(default_factory=list)
    ai_status: str = "disabled"  # "disabled" | "running" | "done" | "failed"
    ai_warning: str | None = None
    ai_model: str | None = None
    batch_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    # See staging_store.py::StagingBatch's identical field.
    has_card_account: bool = False


_batch: RecategorizeBatch | None = None


def create(batch: RecategorizeBatch) -> str:
    global _batch
    if _batch is not None:
        raise ValueError("A recategorize batch is already pending")
    _batch = batch
    return batch.batch_id


def current() -> RecategorizeBatch | None:
    return _batch


def get_by_id(batch_id: str) -> RecategorizeBatch | None:
    """None both when nothing is pending and when a different batch is - the
    background AI task uses this to make itself a no-op once the batch it
    was scheduled for has been committed/discarded/superseded, same guard
    shape as StagingStore.get()'s KeyError-on-mismatch."""
    return _batch if _batch is not None and _batch.batch_id == batch_id else None


def update_row(batch_id: str, transaction_id: int, **fields) -> RecategorizeRow:
    batch = get_by_id(batch_id)
    if batch is None:
        raise KeyError(batch_id)
    row = next((r for r in batch.rows if r.transaction_id == transaction_id), None)
    if row is None:
        raise KeyError(f"No recategorize row for transaction {transaction_id}")
    for key, value in fields.items():
        setattr(row, key, value)
    return row


def delete(batch_id: str) -> None:
    global _batch
    if _batch is not None and _batch.batch_id == batch_id:
        _batch = None


def reset() -> None:
    """Test-only escape hatch - see StagingStore.reset()'s equivalent comment."""
    global _batch
    _batch = None
