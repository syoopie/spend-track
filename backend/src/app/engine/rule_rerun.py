"""Re-applies the categorization rule engine to every eligible row in a
pending staging/recategorize batch - used when a rule is created from the
review dialog (routers/statements.py's and routers/transactions.py's
`.../rules` endpoints) so the new rule doesn't just apply to the one row
that prompted it, but retroactively resolves every other still-open row in
the same batch too.

Deliberately generic over StagingRow and RecategorizeRow (duck-typed via
getattr/setattr on the shared field names both dataclasses happen to
carry - see staging_store.py/recategorize_job.py) rather than importing
either concrete type, so this module stays a sibling of engine/rules.py
instead of depending on either store.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.engine.rules import CategorizationRequest, CategorizationRuleset, categorize

# The fields a categorize() result can change and that a rule-rerun undo
# needs to be able to restore verbatim - mirrors exactly what
# StagingRowUpdateRequest/RecategorizeRowUpdateRequest already let a manual
# row edit touch, minus contact_id (rerun can also assign one via a
# contact-identifier match, so it's included) plus needs_review.
_SNAPSHOT_FIELDS = (
    "category",
    "subcategory",
    "matched_label",
    "is_excluded",
    "exclusion_reason",
    "contact_id",
    "needs_review",
)


@dataclass
class RuleRerunChange:
    key: int
    previous: dict[str, Any]


def rerun_rules_on_batch(
    rows: Sequence[Any],
    key_field: str,
    rules: Sequence[Mapping[str, Any]],
    contact_identifiers: Sequence[Mapping[str, Any]],
    category_directions: Mapping[str, str],
    has_card_account: bool,
) -> list[dict[str, Any]]:
    """Mutates each eligible row in place when re-categorizing it produces a
    different result than what it currently holds, and marks it
    manually_edited so the background AI job can't later clobber a row this
    rule just resolved (see routers/statements.py::_apply_ai_suggestions).
    Rows already resolved by hand (manually_edited) or duplicates are left
    untouched - same "don't override a decision already made" contract the
    AI job itself follows.

    Returns one dict per changed row: {"key": ..., **previous_field_values} -
    everything the caller needs to offer an undo (see
    StagingRuleUndoRequest/RecategorizeRuleUndoRequest in models.py)."""
    ruleset = CategorizationRuleset(
        rules=rules,
        contact_identifiers=contact_identifiers,
        category_directions=category_directions,
        has_card_account=has_card_account,
    )
    changes: list[dict[str, Any]] = []
    for row in rows:
        if getattr(row, "manually_edited", False) or getattr(row, "is_duplicate", False):
            continue
        result = categorize(
            CategorizationRequest(
                raw_description=row.raw_description,
                amount=row.amount,
                posting_account_is_card=row.is_card_account,
            ),
            ruleset,
        )
        after = {
            "category": result.category,
            "subcategory": result.subcategory,
            "matched_label": result.matched_label,
            "is_excluded": result.is_excluded,
            "exclusion_reason": result.exclusion_reason,
            "contact_id": result.contact_id,
            "needs_review": result.needs_review,
        }
        before = {f: getattr(row, f) for f in _SNAPSHOT_FIELDS}
        if before == after:
            continue
        for field, value in after.items():
            setattr(row, field, value)
        row.manually_edited = True
        changes.append({"key": getattr(row, key_field), **before})
    return changes
