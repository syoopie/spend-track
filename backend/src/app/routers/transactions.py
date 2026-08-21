import sqlite3

from fastapi import APIRouter, BackgroundTasks, Query

from app import repo
from app.config import get_ai_settings
from app.db import get_conn
from app.engine import recategorize_job
from app.engine.ai_providers import (
    AiCandidate,
    AiProviderResponseError,
    AiProviderUnavailableError,
    active_model_name,
    build_provider,
)
from app.engine.ai_providers import cancellation as ai_cancellation
from app.engine.paynow import is_paynow_transfer
from app.engine.rules import categorize
from app.errors import api_error
from app.models import (
    RecategorizeBatchOut,
    RecategorizeCommitResult,
    RecategorizeRequest,
    RecategorizeRowOut,
    RecategorizeRowUpdateRequest,
    RefundPairingOut,
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
            RecategorizeRowOut(
                transaction_id=r.transaction_id,
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
                is_paynow=r.is_paynow,
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
        ai_suggested_count=sum(1 for r in batch.rows if r.ai_suggested),
    )


def _run_ai_recategorize(
    batch_id: str, candidates: list[AiCandidate], categories: list[tuple[str, str]], ai_settings: dict
) -> None:
    """Mirrors routers/statements.py::_run_ai_categorization exactly, down to
    the batch-id re-check after the (possibly long) network call: this only
    ever mutates the in-memory pending batch, never the DB - nothing is
    written until commit_recategorize_batch runs."""
    batch = recategorize_job.get_by_id(batch_id)
    if batch is None:
        return  # committed/discarded before the background task even started

    provider = build_provider(ai_settings)
    health = provider.check_health()
    if not health.reachable:
        batch.ai_warning = (
            f"AI is enabled but the model can't be reached ({ai_settings['ai_provider']}: {health.error}) - "
            "results were computed using rules only."
        )
        batch.ai_status = "failed"
        return

    try:
        suggestions = provider.categorize(candidates, categories, cancel_key=batch_id)
    except (AiProviderUnavailableError, AiProviderResponseError) as exc:
        batch.ai_warning = (
            f"AI is enabled but the request failed ({ai_settings['ai_provider']}: {exc}) - "
            "results were computed using rules only."
        )
        batch.ai_status = "failed"
        return

    batch = recategorize_job.get_by_id(batch_id)  # re-check: may have been committed/discarded while thinking
    if batch is None:
        return

    by_id = {r.transaction_id: r for r in batch.rows}
    for suggestion in suggestions:
        row = by_id.get(suggestion.index)
        if row is None:
            continue
        row.category = suggestion.category
        row.matched_label = suggestion.display_label
        row.ai_suggested = True
        row.ai_category = suggestion.category
        row.ai_label = suggestion.display_label
        row.ai_rule_pattern = suggestion.rule_pattern
    batch.ai_status = "done"


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
    same as upload's (see _run_ai_recategorize)."""
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
        rules = repo.fetch_active_rules(conn)
        contact_identifiers = repo.fetch_contact_identifiers(conn)
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

        changed = 0
        ai_candidates: list[AiCandidate] = []
        rows_out: list[recategorize_job.RecategorizeRow] = []
        for row in rows:
            result = categorize(
                row["raw_description"],
                rules,
                contact_identifiers,
                amount=row["amount"],
                category_directions=category_directions,
                has_card_account=has_card_account,
                posting_account_is_card=bool(row["account_is_card"]),
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
                    is_paynow=is_paynow_transfer(row["raw_description"].upper()),
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
    else:
        ai_status = "done" if ai_settings["ai_enabled"] else "disabled"
        ai_model = None

    batch = recategorize_job.RecategorizeBatch(
        date_from=body.date_from,
        date_to=body.date_to,
        account_id=body.account_id,
        scanned=len(rows),
        changed=changed,
        rows=rows_out,
        ai_status=ai_status,
        ai_model=ai_model,
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
        background_tasks.add_task(_run_ai_recategorize, batch.batch_id, ai_candidates, ai_categories, ai_settings)

    return _batch_to_out(batch)


@router.get("/recategorize/current", response_model=RecategorizeBatchOut)
def get_current_recategorize_batch():
    batch = recategorize_job.current()
    if batch is None:
        raise api_error(404, "NO_RECATEGORIZE_BATCH", "No recategorize batch is currently pending.")
    return _batch_to_out(batch)


@router.patch("/recategorize/{batch_id}/rows/{transaction_id}", response_model=RecategorizeBatchOut)
def update_recategorize_row(batch_id: str, transaction_id: int, body: RecategorizeRowUpdateRequest):
    """Mirrors routers/statements.py::update_staging_row exactly - edits the
    in-memory pending row only, never the DB (that only happens on commit)."""
    batch = recategorize_job.get_by_id(batch_id)
    if batch is None:
        raise api_error(404, "RECATEGORIZE_BATCH_NOT_FOUND", "No recategorize batch with that id.")

    row = next((r for r in batch.rows if r.transaction_id == transaction_id), None)
    if row is None:
        raise api_error(404, "RECATEGORIZE_ROW_NOT_FOUND", "No recategorize row for that transaction.")

    # See routers/statements.py::update_staging_row's identical comment - the
    # ai_* fields are a permanent record, never cleared here.
    fields: dict = {"subcategory": body.subcategory, "needs_review": False}
    if body.restore_ai:
        if row.ai_category is None:
            raise api_error(400, "NO_AI_SUGGESTION", "This row has no AI suggestion to restore.")
        fields["category"] = row.ai_category
        fields["matched_label"] = row.ai_label
    elif body.reject_ai:
        fields["category"] = body.category
        fields["matched_label"] = None
    else:
        fields["category"] = body.category
    recategorize_job.update_row(batch_id, transaction_id, **fields)

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
            recategorize_job.update_row(batch_id, transaction_id, contact_id=contact_id)

    return _batch_to_out(recategorize_job.get_by_id(batch_id))


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
