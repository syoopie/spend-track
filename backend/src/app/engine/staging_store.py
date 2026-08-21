"""In-memory pre-commit staging area for uploaded statements.

Not a DB table: TECHNICAL_SPEC.md's schema (§5) has no staging table, and the
UX's "Pre-Commit Staging Review" is inherently transient/discardable. Since
this is a single local process, a batch lives here until committed or
discarded. Known limitation: a batch is lost if the server restarts before
commit - acceptable for a local single-user tool.

Only one batch may be staged at a time - a second upload is rejected until
the pending one is committed or discarded (see routers/statements.py), so
the review UI never has to juggle more than a single pending statement.
"""

import uuid
from dataclasses import dataclass, field


@dataclass
class StagingAccount:
    bank_name: str
    account_number: str  # full/unmasked - used to resolve/provision the real account_id at commit time
    account_number_masked: str
    account_type: str
    is_new: bool  # True if no matching row exists in `accounts` yet


@dataclass
class StagingRow:
    index: int
    account_number: str  # correlates to a StagingAccount.account_number in this batch
    transaction_date: str
    raw_description: str
    matched_label: str | None
    amount: float
    fingerprint: str
    category: str
    subcategory: str | None
    is_excluded: bool
    exclusion_reason: str | None
    contact_id: int | None
    needs_review: bool
    is_duplicate: bool


@dataclass
class StagingBatch:
    source_filename: str
    bank_name: str
    accounts: list[StagingAccount]
    rows: list[StagingRow]
    batch_id: str = field(default_factory=lambda: uuid.uuid4().hex)


class StagingStore:
    def __init__(self) -> None:
        self._batch: StagingBatch | None = None

    def create(self, batch: StagingBatch) -> str:
        if self._batch is not None:
            raise ValueError("A staging batch is already pending")
        self._batch = batch
        return batch.batch_id

    def current(self) -> StagingBatch | None:
        return self._batch

    def get(self, batch_id: str) -> StagingBatch:
        if self._batch is None or self._batch.batch_id != batch_id:
            raise KeyError(batch_id)
        return self._batch

    def update_row(self, batch_id: str, index: int, **fields) -> StagingRow:
        batch = self.get(batch_id)
        row = next((r for r in batch.rows if r.index == index), None)
        if row is None:
            raise KeyError(f"No staging row at index {index}")
        for key, value in fields.items():
            setattr(row, key, value)
        return row

    def delete(self, batch_id: str) -> None:
        if self._batch is not None and self._batch.batch_id == batch_id:
            self._batch = None

    def reset(self) -> None:
        """Test-only escape hatch: this store is a process-wide singleton
        (see get_store below), so tests that don't share a DB still share
        it - each test must clear any pending batch left by a prior one."""
        self._batch = None


_store = StagingStore()


def get_store() -> StagingStore:
    return _store
