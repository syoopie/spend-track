"""In-memory pre-commit staging area for uploaded statements.

Not a DB table: docs/technical-spec.md's schema (§5) has no staging table, and the
UX's "Pre-Commit Staging Review" is inherently transient/discardable. Since
this is a single local process, a batch lives here until committed or
discarded. Known limitation: a batch is lost if the server restarts before
commit - acceptable for a local single-user tool.

Only one batch may be staged at a time - a second upload is rejected until
the pending one is committed or discarded (see routers/statements.py), so
the review UI never has to juggle more than a single pending statement. A
single upload can bundle multiple PDF files (see upload_statement); those
are merged into one batch here rather than tracked as separate batches.

StagingStore's lifecycle (create/get/get_by_id/update_row/delete/reset) is
engine/pending_batch.py's PendingBatchStore, specialized to StagingBatch's
`index`-keyed rows - see that module for the shared implementation, and
engine/recategorize_job.py for the other specialization.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.engine.pending_batch import PendingBatchStore


@dataclass
class StagingAccount:
    bank_name: str
    account_number: str  # full/unmasked - used to resolve/provision the real account_id at commit time
    account_number_masked: str
    account_type: str
    is_new: bool  # True if no matching row exists in `accounts` yet
    is_card: bool = False


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
    # The rules/contact/PayNow engine's answer at row creation, before any AI
    # suggestion or manual edit - permanent, never touched by the update
    # endpoint. This is what "Restore Default" (see ReviewDialog.tsx) resets
    # a row to when there's no ai_category to prefer instead.
    original_category: str
    original_label: str | None
    # Set once at row creation from the raw description's PayNow markers
    # (engine/paynow.py::is_paynow_transfer) and never touched again by the
    # update endpoint - unlike needs_review, which gets cleared to False on
    # any edit, this is what routers/statements.py uses to permanently gate
    # "Save as contact mapping" (PayNow-only) vs. "Save as rule" (everything
    # else) even after the row has already been resolved once.
    is_paynow: bool = False
    # Set once at row creation from the posting account's is_card, same
    # "permanent, never touched by the update endpoint" contract as
    # is_paynow above - engine/rule_rerun.py needs it to re-call categorize()
    # with the right posting_account_is_card without re-deriving it from
    # batch.accounts each time.
    is_card_account: bool = False
    # ai_suggested/ai_category/ai_label/ai_rule_pattern are a permanent record
    # of what the AI proposed for this row - set once by the background AI
    # job and never cleared afterward, even when the user edits over it.
    # That's what lets "Restore Default" (see engine/batch_review.py) bring
    # it back later: "currently showing the AI's suggestion" is derived by
    # comparing category/matched_label against ai_category/ai_label, not
    # tracked as separate mutable state that could drift out of sync.
    ai_suggested: bool = False
    ai_category: str | None = None
    ai_label: str | None = None
    ai_rule_pattern: str | None = None
    # Set by update_row() the moment the user explicitly resolves this row
    # (accept/reject/restore/plain edit) - checked by the background AI job
    # before overwriting a row's category/label, so a suggestion that was
    # still in flight can't clobber a decision the user already made about
    # this specific row while waiting for it (see routers/statements.py's
    # _apply_ai_suggestions).
    manually_edited: bool = False


@dataclass
class StagingBatch:
    source_filenames: list[str]
    bank_name: str
    accounts: list[StagingAccount]
    rows: list[StagingRow]
    batch_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    # When this batch was staged - surfaced by PendingReviewBanner (DASH-6 in
    # UI Review.dc.html) so the banner can say how long ago the upload
    # happened, not just that one is pending.
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # "disabled" (AI off), "running" (background categorization in flight),
    # "done", "failed" (unreachable/errored - see ai_warning). Set once right
    # after the batch is created in upload_statement() and mutated in place
    # by the background task - see routers/statements.py.
    ai_status: str = "disabled"
    ai_warning: str | None = None
    ai_model: str | None = None
    # Whether any card account was known at parse time - see engine/rules.py
    # categorize()'s has_card_account parameter. Stored on the batch (one
    # value for the whole upload) so engine/rule_rerun.py can re-call
    # categorize() later without redoing the accounts-table scan.
    has_card_account: bool = False


class StagingStore(PendingBatchStore[StagingBatch]):
    def __init__(self) -> None:
        super().__init__(row_key_field="index", batch_noun="staging batch", row_noun="staging row at index")


_store = StagingStore()


def get_store() -> StagingStore:
    return _store
