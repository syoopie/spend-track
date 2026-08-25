import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Query

from app import contact_directory, repo, rule_catalog
from app.config import get_ai_settings
from app.db import get_conn
from app.engine import batch_review, recategorize_job
from app.engine.ai_providers import AiCandidate, active_model_name
from app.engine.ai_providers import cancellation as ai_cancellation
from app.engine.batch_review import BatchNotFoundError, InvalidRulePatternError, RowNotFoundError
from app.engine.rules import CategorizationRequest, CategorizationRuleset, categorize
from app.errors import api_error
from app.models import (
    BatchRowOut,
    BatchRowUpdateRequest,
    BatchRuleUndoRequest,
    RecategorizeBatchOut,
    RecategorizeCommitResult,
    RecategorizeRequest,
    RecategorizeRuleCreateResult,
    RefundPairingOut,
    RuleQuickCreateRequest,
    RuleRerunRowSnapshot,
    TransactionOut,
    TransactionUpdateRequest,
)

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def _batch_to_out(batch: recategorize_job.RecategorizeBatch) -> RecategorizeBatchOut:
    return RecategorizeBatchOut(
        batch_id=batch.batch_id,
        date_from=batch.date_from,
        date_to=batch.date_to,
        account_id=batch.account_id,
        scanned=batch.scanned,
        changed=batch.changed,
        rows=[
            BatchRowOut(
                key=r.transaction_id,
                account_number_masked=r.account_number_masked,
                transaction_date=r.transaction_date,
                raw_description=r.raw_description,
                matched_label=r.matched_label,
                amount=r.amount,
                category=r.category,
                subcategory=r.subcategory,
                contact_id=r.contact_id,
                is_excluded=r.is_excluded,
                exclusion_reason=r.exclusion_reason,
                needs_review=r.needs_review,
                # A recategorize batch is built from already-committed
                # transactions, never freshly-parsed rows - dedup only
                # applies to a staging batch (see engine/staging_store.py's
                # StagingRow.is_duplicate).
                is_duplicate=False,
                is_paynow=r.is_paynow,
                original_category=r.original_category,
                original_label=r.original_label,
                ai_suggested=r.ai_suggested,
                ai_category=r.ai_category,
                ai_label=r.ai_label,
                ai_rule_pattern=r.ai_rule_pattern,
            )
            for r in batch.rows
        ],
        ai_status=batch.ai_status,
        ai_warning=batch.ai_warning,
        ai_model=batch.ai_model,
        ai_started_at=batch.ai_started_at,
        ai_suggested_count=sum(1 for r in batch.rows if r.ai_suggested),
    )


def _paired_ids(conn: sqlite3.Connection) -> set[int]:
    ids: set[int] = set()
    for r in conn.execute("SELECT original_transaction_id, refund_transaction_id FROM refund_pairings").fetchall():
        ids.add(r["original_transaction_id"])
        ids.add(r["refund_transaction_id"])
    return ids


def _row_to_out(row: sqlite3.Row, paired_ids: set[int]) -> TransactionOut:
    return TransactionOut(
        id=row["id"],
        account_id=row["account_id"],
        bank_name=row["bank_name"],
        account_number_masked=row["account_number_masked"],
        transaction_date=row["transaction_date"],
        raw_description=row["raw_description"],
        cleaned_description=row["cleaned_description"],
        matched_label=row["matched_label"],
        amount=row["amount"],
        category=row["category"],
        subcategory=row["subcategory"],
        contact_id=row["contact_id"],
        is_excluded=bool(row["is_excluded"]),
        exclusion_reason=row["exclusion_reason"],
        has_refund_link=row["id"] in paired_ids,
    )


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    date_from: str | None = Query(default=None, description="YYYY-MM"),
    date_to: str | None = Query(default=None, description="YYYY-MM"),
    account_id: str | None = None,
    include_excluded: bool = False,
):
    clauses = []
    params: list = []
    if date_from:
        clauses.append("t.transaction_date >= ?")
        params.append(f"{date_from}-01")
    if date_to:
        clauses.append("t.transaction_date <= ?")
        params.append(f"{date_to}-31")
    if account_id:
        clauses.append("t.account_id = ?")
        params.append(account_id)
    if not include_excluded:
        clauses.append("t.is_excluded = 0")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT t.*, a.bank_name AS bank_name, a.account_number_masked AS account_number_masked
            FROM transactions t JOIN accounts a ON a.id = t.account_id
            {where}
            ORDER BY t.transaction_date DESC, t.id DESC
            """,
            params,
        ).fetchall()
        paired_ids = _paired_ids(conn)
        return [_row_to_out(r, paired_ids) for r in rows]


@router.post("/recategorize", response_model=RecategorizeBatchOut)
def recategorize_transactions(body: RecategorizeRequest, background_tasks: BackgroundTasks):
    """Re-runs categorize() against the current rule bank for every committed
    transaction in [date_from, date_to] and stages the proposed result as a
    pending, reviewable batch - exactly the same contract as an upload's
    staging batch (see engine/recategorize_job.py's docstring): nothing is
    written to the transactions table here. The batch is rendered in the
    same ReviewDialog used for staging, with the same Commit/Discard actions
    (see commit_recategorize_batch/discard_recategorize_batch below), and if
    AI is enabled a second pass over whatever's left in the Others/Other
    Income fallback runs in the background against the pending batch's rows,
    same as upload's (see engine/batch_review.py::run_ai_job)."""
    if recategorize_job.current() is not None:
        raise api_error(
            409, "RECATEGORIZE_BATCH_EXISTS", "Commit or discard the pending recategorize batch before running another."
        )

    clauses = ["transaction_date >= ?", "transaction_date <= ?"]
    params: list = [f"{body.date_from}-01", f"{body.date_to}-31"]
    if body.account_id:
        clauses.append("account_id = ?")
        params.append(body.account_id)
    where = " AND ".join(clauses)

    with get_conn() as conn:
        rules = rule_catalog.fetch_active_rules(conn)
        contact_identifiers = contact_directory.fetch_contact_identifiers(conn)
        category_directions = repo.fetch_category_directions(conn)
        ai_categories = repo.fetch_ai_target_categories(conn)
        has_card_account = conn.execute("SELECT 1 FROM accounts WHERE is_card = 1 LIMIT 1").fetchone() is not None
        rows = conn.execute(
            f"""
            SELECT t.*, a.is_card AS account_is_card, a.account_number_masked AS account_number_masked
            FROM transactions t JOIN accounts a ON a.id = t.account_id
            WHERE {where}
            ORDER BY t.transaction_date DESC, t.id DESC
            """,
            params,
        ).fetchall()

        ruleset = CategorizationRuleset(
            rules=rules,
            contact_identifiers=contact_identifiers,
            category_directions=category_directions,
            has_card_account=has_card_account,
        )

        changed = 0
        ai_candidates: list[AiCandidate] = []
        rows_out: list[recategorize_job.RecategorizeRow] = []
        for row in rows:
            result = categorize(
                CategorizationRequest(
                    raw_description=row["raw_description"],
                    amount=row["amount"],
                    posting_account_is_card=bool(row["account_is_card"]),
                ),
                ruleset,
            )
            before = (
                row["category"],
                row["subcategory"],
                row["matched_label"],
                row["contact_id"],
                bool(row["is_excluded"]),
                row["exclusion_reason"],
            )
            after = (
                result.category,
                result.subcategory,
                result.matched_label,
                result.contact_id,
                result.is_excluded,
                result.exclusion_reason,
            )
            if before != after:
                changed += 1
            rows_out.append(
                recategorize_job.RecategorizeRow(
                    transaction_id=row["id"],
                    account_number_masked=row["account_number_masked"],
                    transaction_date=row["transaction_date"],
                    raw_description=row["raw_description"],
                    matched_label=result.matched_label,
                    amount=row["amount"],
                    category=result.category,
                    subcategory=result.subcategory,
                    contact_id=result.contact_id,
                    is_excluded=result.is_excluded,
                    exclusion_reason=result.exclusion_reason,
                    needs_review=result.needs_review,
                    original_category=result.category,
                    original_label=result.matched_label,
                    is_paynow=result.is_paynow,
                    is_card_account=bool(row["account_is_card"]),
                )
            )
            if result.category in ("Others", "Other Income") and result.matched_label is None:
                ai_candidates.append(
                    AiCandidate(
                        index=row["id"],
                        raw_description=row["raw_description"],
                        amount=row["amount"],
                        direction="inflow" if row["amount"] > 0 else "outflow",
                    )
                )

    ai_settings = get_ai_settings()
    if ai_settings["ai_enabled"] and ai_candidates:
        ai_status = "running"
        ai_model = active_model_name(ai_settings)
        ai_started_at = datetime.now(timezone.utc)
    else:
        ai_status = "done" if ai_settings["ai_enabled"] else "disabled"
        ai_model = None
        ai_started_at = None

    batch = recategorize_job.RecategorizeBatch(
        date_from=body.date_from,
        date_to=body.date_to,
        account_id=body.account_id,
        scanned=len(rows),
        changed=changed,
        rows=rows_out,
        ai_status=ai_status,
        ai_model=ai_model,
        ai_started_at=ai_started_at,
        has_card_account=has_card_account,
    )
    try:
        recategorize_job.create(batch)
    except ValueError:
        # Same race-vs-upfront-check translation as statements.py's upload
        # endpoint - the create() call is the actual point of truth.
        raise api_error(
            409, "RECATEGORIZE_BATCH_EXISTS", "Commit or discard the pending recategorize batch before running another."
        )
    if ai_status == "running":
        background_tasks.add_task(
            batch_review.run_ai_job,
            recategorize_job.get_store(),
            batch.batch_id,
            ai_candidates,
            ai_categories,
            ai_settings,
            "results were computed using rules only",
        )

    return _batch_to_out(batch)


@router.get("/recategorize/current", response_model=RecategorizeBatchOut)
def get_current_recategorize_batch():
    batch = recategorize_job.current()
    if batch is None:
        raise api_error(404, "NO_RECATEGORIZE_BATCH", "No recategorize batch is currently pending.")
    return _batch_to_out(batch)


@router.post("/recategorize/{batch_id}/ai/cancel", response_model=RecategorizeBatchOut)
def cancel_recategorize_ai_job(batch_id: str):
    """See statements.py::cancel_staging_ai_job - identical contract, mirrored
    for the recategorize batch's own AI pass."""
    batch = recategorize_job.get_by_id(batch_id)
    if batch is None:
        raise api_error(404, "RECATEGORIZE_BATCH_NOT_FOUND", "No recategorize batch with that id.")
    if batch.ai_status == "running":
        batch.ai_status = "cancelled"
        batch.ai_warning = "AI categorization was cancelled."
        batch.ai_started_at = None
        ai_cancellation.cancel(batch_id)
    return _batch_to_out(batch)


@router.patch("/recategorize/{batch_id}/rows/{transaction_id}", response_model=RecategorizeBatchOut)
def update_recategorize_row(batch_id: str, transaction_id: int, body: BatchRowUpdateRequest):
    """See engine/batch_review.py::apply_row_update - edits the in-memory
    pending row only, never the DB (that only happens on commit)."""
    try:
        batch = batch_review.apply_row_update(recategorize_job.get_store(), batch_id, transaction_id, body)
    except BatchNotFoundError:
        raise api_error(404, "RECATEGORIZE_BATCH_NOT_FOUND", "No recategorize batch with that id.")
    except RowNotFoundError:
        raise api_error(404, "RECATEGORIZE_ROW_NOT_FOUND", "No recategorize row for that transaction.")
    return _batch_to_out(batch)


@router.post("/recategorize/{batch_id}/rules", response_model=RecategorizeRuleCreateResult)
def create_rule_from_recategorize_batch(batch_id: str, body: RuleQuickCreateRequest):
    """See engine/batch_review.py::create_rule_and_rerun."""
    try:
        rule_id, changes, batch = batch_review.create_rule_and_rerun(recategorize_job.get_store(), batch_id, body)
    except BatchNotFoundError:
        raise api_error(404, "RECATEGORIZE_BATCH_NOT_FOUND", "No recategorize batch with that id.")
    except InvalidRulePatternError:
        raise api_error(422, "INVALID_RULE_PATTERN", "Rule pattern cannot be blank.")
    return RecategorizeRuleCreateResult(
        rule_id=rule_id,
        updated_rows=[RuleRerunRowSnapshot(**c) for c in changes],
        batch=_batch_to_out(batch),
    )


@router.post("/recategorize/{batch_id}/rules/undo", response_model=RecategorizeBatchOut)
def undo_rule_from_recategorize_batch(batch_id: str, body: BatchRuleUndoRequest):
    """See engine/batch_review.py::undo_rule."""
    try:
        batch = batch_review.undo_rule(recategorize_job.get_store(), batch_id, body)
    except BatchNotFoundError:
        raise api_error(404, "RECATEGORIZE_BATCH_NOT_FOUND", "No recategorize batch with that id.")
    return _batch_to_out(batch)


@router.post("/recategorize/{batch_id}/commit", response_model=RecategorizeCommitResult)
def commit_recategorize_batch(batch_id: str):
    batch = recategorize_job.get_by_id(batch_id)
    if batch is None:
        raise api_error(404, "RECATEGORIZE_BATCH_NOT_FOUND", "No recategorize batch with that id.")

    with get_conn() as conn:
        for row in batch.rows:
            conn.execute(
                "UPDATE transactions SET category = ?, subcategory = ?, matched_label = ?, contact_id = ?, "
                "is_excluded = ?, exclusion_reason = ? WHERE id = ?",
                (
                    row.category,
                    row.subcategory,
                    row.matched_label,
                    row.contact_id,
                    row.is_excluded,
                    row.exclusion_reason,
                    row.transaction_id,
                ),
            )

    recategorize_job.delete(batch_id)
    ai_cancellation.cancel(batch_id)  # no-op if the AI pass already finished or was never running
    return RecategorizeCommitResult(transactions_committed=len(batch.rows))


@router.delete("/recategorize/{batch_id}", status_code=204)
def discard_recategorize_batch(batch_id: str):
    recategorize_job.delete(batch_id)
    # See statements.py::discard_staging_batch's identical comment - this
    # interrupts an in-flight AI call rather than letting it run to
    # completion for nothing (best-effort, see ai_providers/cancellation.py).
    ai_cancellation.cancel(batch_id)


@router.patch("/{transaction_id}", response_model=TransactionOut)
def update_transaction(transaction_id: int, body: TransactionUpdateRequest):
    with get_conn() as conn:
        existing = conn.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,)).fetchone()
        if existing is None:
            raise api_error(404, "TRANSACTION_NOT_FOUND", "No transaction with that id.")

        is_excluded = body.is_excluded if body.is_excluded is not None else bool(existing["is_excluded"])
        # Unchecking "excluded" clears any stale reason from the last time it was excluded.
        exclusion_reason = (
            None
            if body.is_excluded is False
            else (body.exclusion_reason if body.exclusion_reason is not None else existing["exclusion_reason"])
        )
        conn.execute(
            "UPDATE transactions SET category = ?, subcategory = ?, matched_label = ?, contact_id = ?, "
            "is_excluded = ?, exclusion_reason = ? WHERE id = ?",
            (
                body.category if body.category is not None else existing["category"],
                body.subcategory if body.subcategory is not None else existing["subcategory"],
                body.matched_label if body.matched_label is not None else existing["matched_label"],
                body.contact_id if body.contact_id is not None else existing["contact_id"],
                is_excluded,
                exclusion_reason,
                transaction_id,
            ),
        )

        row = conn.execute(
            """
            SELECT t.*, a.bank_name AS bank_name, a.account_number_masked AS account_number_masked
            FROM transactions t JOIN accounts a ON a.id = t.account_id
            WHERE t.id = ?
            """,
            (transaction_id,),
        ).fetchone()
        paired_ids = _paired_ids(conn)
        return _row_to_out(row, paired_ids)


@router.get("/{transaction_id}/refund-pairing", response_model=RefundPairingOut)
def get_refund_pairing(transaction_id: int):
    with get_conn() as conn:
        pairing = conn.execute(
            "SELECT original_transaction_id, refund_transaction_id FROM refund_pairings "
            "WHERE original_transaction_id = ? OR refund_transaction_id = ?",
            (transaction_id, transaction_id),
        ).fetchone()
        if pairing is None:
            raise api_error(404, "NO_REFUND_PAIRING", "This transaction has no refund pairing.")
        paired_ids = _paired_ids(conn)

        def fetch(tx_id: int) -> TransactionOut:
            row = conn.execute(
                """
                SELECT t.*, a.bank_name AS bank_name, a.account_number_masked AS account_number_masked
                FROM transactions t JOIN accounts a ON a.id = t.account_id
                WHERE t.id = ?
                """,
                (tx_id,),
            ).fetchone()
            return _row_to_out(row, paired_ids)

        return RefundPairingOut(
            original=fetch(pairing["original_transaction_id"]),
            refund=fetch(pairing["refund_transaction_id"]),
        )
