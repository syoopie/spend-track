"""Generic lifecycle for an in-memory, pre-commit pending batch.

Both a statement upload's staging batch (engine/staging_store.py) and a
recategorize run's pending batch (engine/recategorize_job.py) are the same
shape - create one, look it up by id, mutate a row in place, delete it - and
had that create/current/get/get_by_id/update_row/delete/reset bookkeeping
implemented twice with identical logic. This module is the one place that
logic lives now; see CONTEXT.md's PendingBatch entry.

Deliberately NOT a shared singleton: each caller instantiates its own
PendingBatchStore, so a staging batch and a recategorize batch can still be
pending at the same time (each only guards against a second batch of its own
kind) - that's an intentional, user-visible behavior kept as-is, not an
oversight.
"""

from typing import Any, Generic, Protocol, TypeVar


class _HasBatchId(Protocol):
    batch_id: str
    rows: list


B = TypeVar("B", bound=_HasBatchId)


class PendingBatchStore(Generic[B]):
    def __init__(self, row_key_field: str, batch_noun: str, row_noun: str) -> None:
        self._batch: B | None = None
        # Public: engine/batch_review.py looks this up generically (row
        # lookups, and to tell rerun_rules_on_batch which field a changed
        # row's "key" is) without needing to know StagingRow from
        # RecategorizeRow.
        self.row_key_field = row_key_field
        self._batch_noun = batch_noun
        self._row_noun = row_noun

    def create(self, batch: B) -> str:
        if self._batch is not None:
            raise ValueError(f"A {self._batch_noun} is already pending")
        self._batch = batch
        return batch.batch_id

    def current(self) -> B | None:
        return self._batch

    def get(self, batch_id: str) -> B:
        if self._batch is None or self._batch.batch_id != batch_id:
            raise KeyError(batch_id)
        return self._batch

    def get_by_id(self, batch_id: str) -> B | None:
        """None both when nothing is pending and when a different batch is -
        for callers (like the background AI job) that want to become a no-op
        once the batch they were scheduled for has been superseded, without
        having to catch KeyError from get()."""
        return self._batch if self._batch is not None and self._batch.batch_id == batch_id else None

    def update_row(self, batch_id: str, key: Any, **fields: Any) -> Any:
        batch = self.get(batch_id)
        row = next((r for r in batch.rows if getattr(r, self.row_key_field) == key), None)
        if row is None:
            raise KeyError(f"No {self._row_noun} {key}")
        for field_name, value in fields.items():
            setattr(row, field_name, value)
        return row

    def delete(self, batch_id: str) -> None:
        if self._batch is not None and self._batch.batch_id == batch_id:
            self._batch = None

    def reset(self) -> None:
        """Test-only escape hatch: process-wide singleton stores built on top
        of this class are shared across tests, so each test must clear any
        pending batch left by a prior one."""
        self._batch = None
