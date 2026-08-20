"""In-memory pre-commit staging area for uploaded statements.

Not a DB table: TECHNICAL_SPEC.md's schema (§5) has no staging table, and the
UX's "Pre-Commit Staging Review" is inherently transient/discardable. Since
this is a single local process, a batch lives here until committed or
discarded. Known limitation: a batch is lost if the server restarts before
commit - acceptable for a local single-user tool.
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
        self._batches: dict[str, StagingBatch] = {}

    def create(self, batch: StagingBatch) -> str:
        self._batches[batch.batch_id] = batch
        return batch.batch_id

    def get(self, batch_id: str) -> StagingBatch:
        return self._batches[batch_id]

    def update_row(self, batch_id: str, index: int, **fields) -> StagingRow:
        batch = self.get(batch_id)
        row = next((r for r in batch.rows if r.index == index), None)
        if row is None:
            raise KeyError(f"No staging row at index {index}")
        for key, value in fields.items():
            setattr(row, key, value)
        return row

    def delete(self, batch_id: str) -> None:
        self._batches.pop(batch_id, None)


_store = StagingStore()


def get_store() -> StagingStore:
    return _store
