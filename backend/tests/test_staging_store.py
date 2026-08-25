import pytest

from app.engine.staging_store import StagingAccount, StagingBatch, StagingRow, StagingStore


def make_batch():
    return StagingBatch(
        source_filenames=["statement.pdf"],
        bank_name="UOB",
        accounts=[
            StagingAccount(
                bank_name="UOB",
                account_number="770-331-567-8",
                account_number_masked="••5678",
                account_type="One Account",
                is_new=True,
            )
        ],
        rows=[
            StagingRow(
                index=0,
                account_number="770-331-567-8",
                source_filename="statement.pdf",
                transaction_date="2026-05-05",
                raw_description="Grab",
                matched_label="Grab",
                amount=-24.80,
                fingerprint="abc123",
                category="Transport",
                subcategory=None,
                is_excluded=False,
                exclusion_reason=None,
                contact_id=None,
                needs_review=False,
                is_duplicate=False,
                original_category="Transport",
                original_label="Grab",
            )
        ],
    )


def test_create_and_get_roundtrip():
    store = StagingStore()
    batch = make_batch()
    batch_id = store.create(batch)
    assert store.get(batch_id) is batch


def test_get_missing_batch_raises_keyerror():
    store = StagingStore()
    with pytest.raises(KeyError):
        store.get("does-not-exist")


def test_update_row_mutates_in_place():
    store = StagingStore()
    batch = make_batch()
    batch_id = store.create(batch)
    store.update_row(batch_id, 0, category="Dining", subcategory="Coffee")
    row = store.get(batch_id).rows[0]
    assert row.category == "Dining"
    assert row.subcategory == "Coffee"


def test_update_missing_row_raises_keyerror():
    store = StagingStore()
    batch_id = store.create(make_batch())
    with pytest.raises(KeyError):
        store.update_row(batch_id, 99, category="X")


def test_delete_removes_batch():
    store = StagingStore()
    batch_id = store.create(make_batch())
    store.delete(batch_id)
    with pytest.raises(KeyError):
        store.get(batch_id)
