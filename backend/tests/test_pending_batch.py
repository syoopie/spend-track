from dataclasses import dataclass, field

import pytest

from app.engine.pending_batch import PendingBatchStore


@dataclass
class _Row:
    key: str
    value: int = 0


@dataclass
class _Batch:
    rows: list[_Row]
    batch_id: str = field(default_factory=lambda: "batch-1")


def make_store() -> PendingBatchStore[_Batch]:
    return PendingBatchStore(row_key_field="key", batch_noun="test batch", row_noun="test row for key")


def make_batch(batch_id: str = "batch-1") -> _Batch:
    return _Batch(rows=[_Row(key="a", value=1)], batch_id=batch_id)


def test_create_and_get_roundtrip():
    store = make_store()
    batch = make_batch()
    batch_id = store.create(batch)
    assert store.get(batch_id) is batch
    assert store.current() is batch


def test_create_rejects_a_second_pending_batch():
    store = make_store()
    store.create(make_batch("batch-1"))
    with pytest.raises(ValueError, match="A test batch is already pending"):
        store.create(make_batch("batch-2"))


def test_get_missing_batch_raises_keyerror():
    store = make_store()
    with pytest.raises(KeyError):
        store.get("does-not-exist")


def test_get_by_id_returns_none_when_missing_or_mismatched():
    store = make_store()
    assert store.get_by_id("anything") is None
    store.create(make_batch("batch-1"))
    assert store.get_by_id("other-batch") is None
    assert store.get_by_id("batch-1") is not None


def test_update_row_mutates_in_place():
    store = make_store()
    batch_id = store.create(make_batch())
    store.update_row(batch_id, "a", value=99)
    assert store.get(batch_id).rows[0].value == 99


def test_update_missing_row_raises_keyerror():
    store = make_store()
    batch_id = store.create(make_batch())
    with pytest.raises(KeyError):
        store.update_row(batch_id, "does-not-exist", value=1)


def test_delete_removes_batch():
    store = make_store()
    batch_id = store.create(make_batch())
    store.delete(batch_id)
    assert store.current() is None
    with pytest.raises(KeyError):
        store.get(batch_id)


def test_delete_ignores_mismatched_batch_id():
    store = make_store()
    batch_id = store.create(make_batch())
    store.delete("some-other-id")
    assert store.get(batch_id) is not None


def test_reset_clears_pending_batch():
    store = make_store()
    store.create(make_batch())
    store.reset()
    assert store.current() is None


def test_two_stores_are_independent_singleton_slots():
    """Mirrors the decided PendingBatch behavior: a staging batch and a
    recategorize batch may be pending at the same time - two independent
    PendingBatchStore instances must not interfere with each other."""
    staging = make_store()
    recategorize = make_store()
    staging.create(make_batch("staging-batch"))
    recategorize.create(make_batch("recategorize-batch"))
    assert staging.current().batch_id == "staging-batch"
    assert recategorize.current().batch_id == "recategorize-batch"
    staging.delete("staging-batch")
    assert staging.current() is None
    assert recategorize.current() is not None
