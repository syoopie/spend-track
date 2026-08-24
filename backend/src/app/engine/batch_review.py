"""Deepens the PendingBatch seam one layer past engine/pending_batch.py:
the actions available on any pending batch under review - apply one row's
edit, create a rule and rerun it across the batch, undo a rule creation, and
apply a background AI job's suggestions - had their implementations
duplicated verbatim between routers/statements.py (staging) and
routers/transactions.py (recategorize) even after the storage layer
(PendingBatchStore) and row/request shapes (BatchRowOut, BatchRowUpdateRequest,
BatchRuleUndoRequest) were unified in an earlier pass. This module is the one
implementation, generic over any PendingBatchStore; both routers now call in
and wrap the result in their own batch-specific response type
(StagingBatchOut/RecategorizeBatchOut - those still differ genuinely, since
their batch-level metadata is genuinely different shapes, so this module
never builds a response itself)."""

from typing import Any

from app import contact_directory, repo, rule_catalog
from app.db import get_conn
from app.engine.ai_providers import AiCandidate, AiSuggestion, run_categorization_job
from app.engine.pending_batch import PendingBatchStore
from app.engine.rule_rerun import rerun_rules_on_batch
from app.models import BatchRowUpdateRequest, BatchRuleUndoRequest, RuleQuickCreateRequest


class BatchNotFoundError(Exception):
    pass


class RowNotFoundError(Exception):
    pass


class InvalidRulePatternError(Exception):
    pass


def _get_batch(store: PendingBatchStore, batch_id: str) -> Any:
    try:
        return store.get(batch_id)
    except KeyError:
        raise BatchNotFoundError(batch_id) from None


def _find_row(store: PendingBatchStore, batch: Any, key: Any) -> Any:
    row = next((r for r in batch.rows if getattr(r, store.row_key_field) == key), None)
    if row is None:
        raise RowNotFoundError(key)
    return row


def apply_row_update(store: PendingBatchStore, batch_id: str, key: Any, body: BatchRowUpdateRequest) -> Any:
    """Applies one row's edit within a pending batch: either a plain
    category/matched_label edit, or the single "Restore Default" action -
    then optionally saves the edit as a persistent rule and/or contact
    mapping. Returns the batch (unchanged identity, mutated in place) so the
    caller can build its own response type from it.

    ai_suggested/ai_category/ai_label/ai_rule_pattern and
    original_category/original_label are never cleared here - they're
    permanent records (of what the AI proposed, and of the rules engine's
    original answer) that a manual edit can always be reverted back to via
    restore_default: prefers the AI suggestion when one exists, else falls
    back to the original. manually_edited locks this row out of the
    background AI job's apply step (see apply_ai_suggestions below) - once
    the user has explicitly acted on a row, an AI suggestion that was still
    in flight when they did can't silently overwrite that decision."""
    batch = _get_batch(store, batch_id)
    row = _find_row(store, batch, key)

    fields: dict = {"subcategory": body.subcategory, "needs_review": False, "manually_edited": True}
    if body.restore_default:
        if row.ai_category is not None:
            fields["category"] = row.ai_category
            fields["matched_label"] = row.ai_label
        else:
            fields["category"] = row.original_category
            fields["matched_label"] = row.original_label
    else:
        fields["category"] = body.category
        fields["matched_label"] = body.matched_label
    store.update_row(batch_id, key, **fields)

    with get_conn() as conn:
        contact_id = repo.apply_save_as_rule_and_contact(
            conn,
            raw_description=row.raw_description,
            category=body.category,
            subcategory=body.subcategory,
            save_as_rule=body.save_as_rule,
            rule_pattern=body.rule_pattern,
            rule_priority=body.rule_priority,
            save_as_contact=body.save_as_contact,
            contact_name=body.contact_name,
            contact_identifier=body.contact_identifier,
        )
        if contact_id is not None:
            store.update_row(batch_id, key, contact_id=contact_id)

    return batch


def create_rule_and_rerun(store: PendingBatchStore, batch_id: str, body: RuleQuickCreateRequest) -> tuple[int, list[dict], Any]:
    """The review dialog's "Create Rule" action - a separate, explicit step
    from applying a category to one row (see ReviewDialog.tsx): creates a
    persistent rule, then immediately re-runs categorize() against every
    other still-unresolved row in this batch so the new rule doesn't just
    affect the one transaction that prompted it. Returns (rule_id, changes,
    batch) - changes is rerun_rules_on_batch's per-row previous-values list,
    for the caller to build an undo prompt from."""
    batch = _get_batch(store, batch_id)
    if not body.match_pattern.strip():
        raise InvalidRulePatternError()

    with get_conn() as conn:
        rule_id = rule_catalog.insert_rule(
            conn,
            priority=rule_catalog.next_user_rule_priority(conn),
            match_pattern=body.match_pattern.strip(),
            target_category=body.target_category,
            target_subcategory=body.target_subcategory,
            direction=rule_catalog.category_direction(conn, body.target_category),
            display_label=body.display_label,
        )
        rules = rule_catalog.fetch_active_rules(conn)
        contact_identifiers = contact_directory.fetch_contact_identifiers(conn)
        category_directions = repo.fetch_category_directions(conn)

    changes = rerun_rules_on_batch(
        batch.rows, store.row_key_field, rules, contact_identifiers, category_directions, batch.has_card_account
    )
    return rule_id, changes, batch


def undo_rule(store: PendingBatchStore, batch_id: str, body: BatchRuleUndoRequest) -> Any:
    """Reverses exactly one create_rule_and_rerun call: deletes the rule it
    created and restores every row it touched to the previous values that
    call returned - the caller passes those straight back, never
    recomputing them itself."""
    batch = _get_batch(store, batch_id)

    with get_conn() as conn:
        conn.execute("DELETE FROM rules WHERE id = ? AND is_default = 0", (body.rule_id,))

    for snap in body.rows:
        try:
            store.update_row(
                batch_id,
                snap.key,
                category=snap.category,
                subcategory=snap.subcategory,
                matched_label=snap.matched_label,
                is_excluded=snap.is_excluded,
                exclusion_reason=snap.exclusion_reason,
                contact_id=snap.contact_id,
                needs_review=snap.needs_review,
                manually_edited=False,
            )
        except KeyError:
            continue  # row no longer exists - nothing left to restore for it
    return batch


def apply_ai_suggestions(store: PendingBatchStore, batch: Any, suggestions: list[AiSuggestion]) -> None:
    by_key = {getattr(r, store.row_key_field): r for r in batch.rows}
    for suggestion in suggestions:
        row = by_key.get(suggestion.index)
        if row is None or row.manually_edited:
            continue  # unknown row, or the user already resolved it while the model was thinking
        row.category = suggestion.category
        row.matched_label = suggestion.display_label
        row.ai_suggested = True
        row.ai_category = suggestion.category
        row.ai_label = suggestion.display_label
        row.ai_rule_pattern = suggestion.rule_pattern


def run_ai_job(
    store: PendingBatchStore,
    batch_id: str,
    candidates: list[AiCandidate],
    categories: list[tuple[str, str]],
    ai_settings: dict,
    fallback_description: str,
) -> None:
    """Background-task entrypoint for both statements.py's upload and
    transactions.py's recategorize: store.get_by_id already has the
    "None once superseded" contract run_categorization_job's get_batch
    needs, so the only per-caller state is the store itself and the
    fallback wording."""
    run_categorization_job(
        batch_id,
        get_batch=store.get_by_id,
        apply_suggestions=lambda batch, suggestions: apply_ai_suggestions(store, batch, suggestions),
        candidates=candidates,
        categories=categories,
        ai_settings=ai_settings,
        fallback_description=fallback_description,
    )
