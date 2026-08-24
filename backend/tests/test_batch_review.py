"""Direct unit tests for engine/batch_review.py - previously this logic
(apply-row-update, create-rule-and-rerun, undo-rule, apply-ai-suggestions)
was only reachable through full router+TestClient integration tests
(test_ai_categorization_integration.py, test_statements_router.py,
test_crud_routers.py) once per batch kind. These exercise the one shared
implementation directly, and - since it's generic over any
PendingBatchStore - against both a real StagingStore and a bespoke store
shape, to prove it's genuinely store-agnostic rather than staging-shaped
with recategorize duct-taped on."""

from dataclasses import dataclass, field

import pytest

from app.engine import batch_review, recategorize_job
from app.engine.batch_review import (
    BatchNotFoundError,
    InvalidRulePatternError,
    RowNotFoundError,
)
from app.engine.pending_batch import PendingBatchStore
from app.engine.staging_store import StagingAccount, StagingBatch, StagingRow, get_store
from app.db import init_db
from app.models import BatchRowUpdateRequest, BatchRuleUndoRequest, RuleQuickCreateRequest, RuleRerunRowSnapshot


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("SG_TRACKER_DB_PATH", str(db_path))
    init_db(db_path)
    return db_path


def make_staging_row(index: int, raw_description: str = "GRAB RIDE", amount: float = -10.0, **overrides) -> StagingRow:
    fields = dict(
        index=index,
        account_number="1234567890",
        transaction_date="2024-01-01",
        raw_description=raw_description,
        matched_label=None,
        amount=amount,
        fingerprint=f"fp{index}",
        category="Others" if amount < 0 else "Other Income",
        subcategory=None,
        is_excluded=False,
        exclusion_reason=None,
        contact_id=None,
        needs_review=False,
        is_duplicate=False,
        original_category="Others" if amount < 0 else "Other Income",
        original_label=None,
    )
    fields.update(overrides)
    return StagingRow(**fields)


def make_staging_batch(rows: list[StagingRow]) -> StagingBatch:
    return StagingBatch(
        source_filenames=["f.pdf"],
        bank_name="UOB",
        accounts=[StagingAccount(bank_name="UOB", account_number="1234567890", account_number_masked="••7890", account_type="Savings", is_new=True)],
        rows=rows,
    )


# --- apply_row_update -----------------------------------------------------


def test_apply_row_update_applies_category_and_clears_needs_review(db):
    store = get_store()
    row = make_staging_row(0, needs_review=True)
    batch_id = store.create(make_staging_batch([row]))

    batch_review.apply_row_update(store, batch_id, 0, BatchRowUpdateRequest(category="Shopping"))

    assert row.category == "Shopping"
    assert row.needs_review is False
    assert row.manually_edited is True


def test_apply_row_update_can_edit_label_alongside_category(db):
    store = get_store()
    row = make_staging_row(0)
    batch_id = store.create(make_staging_batch([row]))

    batch_review.apply_row_update(
        store, batch_id, 0, BatchRowUpdateRequest(category="Shopping", matched_label="My Label")
    )

    assert row.category == "Shopping"
    assert row.matched_label == "My Label"


def test_apply_row_update_manual_edit_over_ai_suggestion_keeps_ai_record(db):
    store = get_store()
    row = make_staging_row(0, ai_suggested=True, ai_category="Shopping", ai_label="AI Label")
    batch_id = store.create(make_staging_batch([row]))

    batch_review.apply_row_update(store, batch_id, 0, BatchRowUpdateRequest(category="Others", matched_label=None))

    assert row.category == "Others"
    assert row.matched_label is None
    assert row.ai_suggested is True  # permanent record, not cleared
    assert row.ai_category == "Shopping"


def test_apply_row_update_restore_default_prefers_ai_suggestion(db):
    store = get_store()
    row = make_staging_row(0, ai_suggested=True, ai_category="Shopping", ai_label="AI Label")
    batch_id = store.create(make_staging_batch([row]))
    # Manually diverge from the AI suggestion first.
    batch_review.apply_row_update(store, batch_id, 0, BatchRowUpdateRequest(category="Others", matched_label=None))

    batch_review.apply_row_update(store, batch_id, 0, BatchRowUpdateRequest(category="Others", restore_default=True))

    assert row.category == "Shopping"
    assert row.matched_label == "AI Label"


def test_apply_row_update_restore_default_falls_back_to_original_without_ai(db):
    store = get_store()
    row = make_staging_row(0, original_category="Groceries", original_label="Original Label")
    batch_id = store.create(make_staging_batch([row]))
    # Manually diverge from the original first.
    batch_review.apply_row_update(store, batch_id, 0, BatchRowUpdateRequest(category="Shopping", matched_label="Edited"))

    batch_review.apply_row_update(store, batch_id, 0, BatchRowUpdateRequest(category="Shopping", restore_default=True))

    assert row.category == "Groceries"
    assert row.matched_label == "Original Label"


def test_apply_row_update_missing_batch_raises(db):
    store = get_store()
    with pytest.raises(BatchNotFoundError):
        batch_review.apply_row_update(store, "does-not-exist", 0, BatchRowUpdateRequest(category="Others"))


def test_apply_row_update_missing_row_raises(db):
    store = get_store()
    batch_id = store.create(make_staging_batch([make_staging_row(0)]))
    with pytest.raises(RowNotFoundError):
        batch_review.apply_row_update(store, batch_id, 99, BatchRowUpdateRequest(category="Others"))


def test_apply_row_update_save_as_rule_persists_a_rule(db):
    store = get_store()
    row = make_staging_row(0, raw_description="NTUC FAIRPRICE")
    batch_id = store.create(make_staging_batch([row]))

    batch_review.apply_row_update(
        store,
        batch_id,
        0,
        BatchRowUpdateRequest(category="Groceries", save_as_rule=True, rule_pattern="FAIRPRICE"),
    )

    from app import rule_catalog
    from app.db import _connect

    conn = _connect(db)
    rules = rule_catalog.fetch_active_rules(conn)
    assert any(r["match_pattern"] == "FAIRPRICE" and r["target_category"] == "Groceries" for r in rules)


# --- create_rule_and_rerun -------------------------------------------------


def test_create_rule_and_rerun_reruns_other_open_rows(db):
    store = get_store()
    # The row that prompted "Create Rule" has already been resolved via a
    # prior apply_row_update call (manually_edited=True) - matches the real
    # ReviewDialog flow, and keeps it out of rerun_rules_on_batch's own scope.
    prompting_row = make_staging_row(0, raw_description="STARBUCKS SG", category="Dining", manually_edited=True)
    other_open_row = make_staging_row(1, raw_description="STARBUCKS ORCHARD")
    resolved_row = make_staging_row(2, raw_description="STARBUCKS RAFFLES", manually_edited=True)
    batch_id = store.create(make_staging_batch([prompting_row, other_open_row, resolved_row]))

    rule_id, changes, batch = batch_review.create_rule_and_rerun(
        store, batch_id, RuleQuickCreateRequest(match_pattern="STARBUCKS", target_category="Dining")
    )

    assert rule_id > 0
    assert other_open_row.category == "Dining"
    assert other_open_row.manually_edited is True
    assert {c["key"] for c in changes} == {1}  # only the still-open row changed
    assert resolved_row.category != "Dining"  # already resolved, left alone
    assert batch is store.get(batch_id)


def test_create_rule_and_rerun_carries_display_label_into_rule(db):
    store = get_store()
    prompting_row = make_staging_row(0, raw_description="STARBUCKS SG", category="Dining", manually_edited=True)
    other_open_row = make_staging_row(1, raw_description="STARBUCKS ORCHARD")
    batch_id = store.create(make_staging_batch([prompting_row, other_open_row]))

    batch_review.create_rule_and_rerun(
        store,
        batch_id,
        RuleQuickCreateRequest(match_pattern="STARBUCKS", target_category="Dining", display_label="Starbucks"),
    )

    assert other_open_row.matched_label == "Starbucks"


def test_create_rule_and_rerun_rejects_blank_pattern(db):
    store = get_store()
    batch_id = store.create(make_staging_batch([make_staging_row(0)]))
    with pytest.raises(InvalidRulePatternError):
        batch_review.create_rule_and_rerun(
            store, batch_id, RuleQuickCreateRequest(match_pattern="   ", target_category="Dining")
        )


def test_create_rule_and_rerun_missing_batch_raises(db):
    store = get_store()
    with pytest.raises(BatchNotFoundError):
        batch_review.create_rule_and_rerun(
            store, "does-not-exist", RuleQuickCreateRequest(match_pattern="X", target_category="Dining")
        )


# --- undo_rule --------------------------------------------------------------


def test_undo_rule_deletes_rule_and_restores_previous_values(db):
    store = get_store()
    prompting_row = make_staging_row(0, raw_description="STARBUCKS SG", category="Dining", manually_edited=True)
    other_open_row = make_staging_row(1, raw_description="STARBUCKS ORCHARD")
    batch_id = store.create(make_staging_batch([prompting_row, other_open_row]))

    rule_id, changes, _batch = batch_review.create_rule_and_rerun(
        store, batch_id, RuleQuickCreateRequest(match_pattern="STARBUCKS", target_category="Dining")
    )
    assert other_open_row.category == "Dining"

    batch_review.undo_rule(
        store, batch_id, BatchRuleUndoRequest(rule_id=rule_id, rows=[RuleRerunRowSnapshot(**c) for c in changes])
    )

    assert other_open_row.category == "Others"
    assert other_open_row.manually_edited is False

    from app import rule_catalog
    from app.db import _connect

    conn = _connect(db)
    assert not any(r["id"] == rule_id for r in rule_catalog.fetch_active_rules(conn))


def test_undo_rule_ignores_rows_that_no_longer_exist(db):
    store = get_store()
    batch_id = store.create(make_staging_batch([make_staging_row(0)]))
    # Nothing raises even though key 99 was never a real row.
    batch_review.undo_rule(
        store,
        batch_id,
        BatchRuleUndoRequest(
            rule_id=1,
            rows=[
                RuleRerunRowSnapshot(
                    key=99, category="Others", subcategory=None, matched_label=None,
                    is_excluded=False, exclusion_reason=None, contact_id=None, needs_review=False,
                )
            ],
        ),
    )


# --- apply_ai_suggestions: generic over any PendingBatchStore shape --------


@dataclass
class _BareRow:
    key: int
    category: str = "Others"
    matched_label: str | None = None
    ai_suggested: bool = False
    ai_category: str | None = None
    ai_label: str | None = None
    ai_rule_pattern: str | None = None
    manually_edited: bool = False


@dataclass
class _BareBatch:
    rows: list[_BareRow]
    batch_id: str = field(default_factory=lambda: "bare-batch")


def test_apply_ai_suggestions_is_generic_over_the_store_shape():
    """Not StagingRow or RecategorizeRow at all - proves apply_ai_suggestions
    only depends on store.row_key_field + the small set of ai_* attributes,
    not on which concrete batch kind it's given."""
    from app.engine.ai_providers.base import AiSuggestion

    store = PendingBatchStore(row_key_field="key", batch_noun="bare batch", row_noun="bare row")
    edited = _BareRow(key=1, manually_edited=True)
    untouched = _BareRow(key=2)
    batch = _BareBatch(rows=[edited, untouched])

    batch_review.apply_ai_suggestions(
        store,
        batch,
        [
            AiSuggestion(index=1, category="Shopping", display_label="Should not apply", rule_pattern=None),
            AiSuggestion(index=2, category="Shopping", display_label="Should apply", rule_pattern=None),
            AiSuggestion(index=999, category="Shopping", display_label="Unknown row", rule_pattern=None),
        ],
    )

    assert edited.category == "Others"
    assert untouched.category == "Shopping"
    assert untouched.matched_label == "Should apply"
    assert untouched.ai_suggested is True


# --- recategorize_job.get_store() ------------------------------------------


def test_recategorize_job_get_store_returns_the_same_singleton():
    assert recategorize_job.get_store() is recategorize_job.get_store()
    batch_id = recategorize_job.create(
        recategorize_job.RecategorizeBatch(date_from="2024-01", date_to="2024-01", account_id=None, scanned=0, changed=0)
    )
    assert recategorize_job.get_store().get(batch_id) is recategorize_job.current()
