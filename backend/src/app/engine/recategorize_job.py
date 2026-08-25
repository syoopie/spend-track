"""In-memory pending batch for a recategorize run - the row/batch shape and
lifecycle (create/get/get_by_id/update_row/delete/reset, "only one pending
batch at a time") live in engine/pending_batch.py's PendingBatchStore, shared
with engine/staging_store.py's StagingStore; only the RecategorizeRow/
RecategorizeBatch shapes and this module's process-wide singleton slot are
specific to a recategorize run. Recategorize is meant to behave identically
to an upload from the app's perspective: nothing is written to the
transactions table until the batch is explicitly committed via
routers/transactions.py::commit_recategorize_batch, and discarding it (or
letting a background AI pass be cancelled - see ai_providers/cancellation.py)
leaves the DB completely untouched.

Kept as its own singleton slot rather than merged with StagingStore's - a
staging batch and a recategorize batch may be pending at the same time, each
only guarding against a second batch of its own kind. Deliberate: unifying
to "one pending batch of any kind" would change user-facing behavior for no
real benefit.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.engine.pending_batch import PendingBatchStore


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
    # See staging_store.py::StagingRow's identical fields - the rules
    # engine's freshly-recomputed answer at row creation, permanent, never
    # touched by the update endpoint.
    original_category: str
    original_label: str | None
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
    ai_status: str = "disabled"  # "disabled" | "running" | "done" | "failed" | "cancelled"
    ai_warning: str | None = None
    ai_model: str | None = None
    # See staging_store.py::StagingBatch's identical field.
    ai_started_at: datetime | None = None
    batch_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    # See staging_store.py::StagingBatch's identical field.
    has_card_account: bool = False


_store: PendingBatchStore[RecategorizeBatch] = PendingBatchStore(
    row_key_field="transaction_id", batch_noun="recategorize batch", row_noun="recategorize row for transaction"
)


def get_store() -> PendingBatchStore[RecategorizeBatch]:
    """Exposes the singleton itself - see staging_store.py's get_store() -
    so engine/batch_review.py can operate on either kind of pending batch
    generically instead of every caller going through this module's
    per-field wrapper functions."""
    return _store


def create(batch: RecategorizeBatch) -> str:
    return _store.create(batch)


def current() -> RecategorizeBatch | None:
    return _store.current()


def get_by_id(batch_id: str) -> RecategorizeBatch | None:
    """None both when nothing is pending and when a different batch is - the
    background AI task uses this to make itself a no-op once the batch it
    was scheduled for has been committed/discarded/superseded, same guard
    shape as StagingStore.get()'s KeyError-on-mismatch."""
    return _store.get_by_id(batch_id)


def update_row(batch_id: str, transaction_id: int, **fields) -> RecategorizeRow:
    return _store.update_row(batch_id, transaction_id, **fields)


def delete(batch_id: str) -> None:
    _store.delete(batch_id)


def reset() -> None:
    """Test-only escape hatch - see StagingStore.reset()'s equivalent comment."""
    _store.reset()
