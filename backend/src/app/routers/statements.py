import sqlite3

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.db import get_conn
from app.engine.fingerprint import clean_description, compute_daily_sequence_indices, compute_fingerprint
from app.engine.identity import derive_account_id
from app.engine.naming import extract_display_name
from app.engine.refunds import find_refund_pairs
from app.engine.rules import categorize
from app.engine.staging_store import StagingAccount, StagingBatch, StagingRow, get_store
from app.models import (
    CommitResult,
    StagingAccountOut,
    StagingBatchOut,
    StagingRowOut,
    StagingRowUpdateRequest,
)
from app.parsing.base import UnparseableStatementError
from app.parsing.pdf_io import EncryptedPdfError, IncorrectPasswordError, open_pdf
from app.parsing.registry import detect_and_parse

router = APIRouter(prefix="/api/statements", tags=["statements"])


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _fetch_active_rules(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM rules ORDER BY priority ASC").fetchall()


def _fetch_contact_identifiers(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT ci.identifier AS identifier, c.id AS contact_id, c.name AS name,
               c.default_category AS default_category, c.default_subcategory AS default_subcategory
        FROM contact_identifiers ci JOIN contacts c ON c.id = ci.contact_id
        """
    ).fetchall()


def _batch_to_response(batch: StagingBatch) -> StagingBatchOut:
    masked_by_number = {a.account_number: a.account_number_masked for a in batch.accounts}
    rows_out = [
        StagingRowOut(
            index=r.index,
            account_number_masked=masked_by_number[r.account_number],
            transaction_date=r.transaction_date,
            raw_description=r.raw_description,
            matched_label=r.matched_label,
            amount=r.amount,
            category=r.category,
            subcategory=r.subcategory,
            is_excluded=r.is_excluded,
            exclusion_reason=r.exclusion_reason,
            contact_id=r.contact_id,
            needs_review=r.needs_review,
            is_duplicate=r.is_duplicate,
        )
        for r in batch.rows
    ]
    return StagingBatchOut(
        batch_id=batch.batch_id,
        source_filename=batch.source_filename,
        bank_name=batch.bank_name,
        accounts=[
            StagingAccountOut(
                bank_name=a.bank_name,
                account_number_masked=a.account_number_masked,
                account_type=a.account_type,
                is_new=a.is_new,
            )
            for a in batch.accounts
        ],
        rows=rows_out,
        new_extracted=sum(1 for r in batch.rows if not r.is_duplicate),
        duplicates_skipped=sum(1 for r in batch.rows if r.is_duplicate),
        new_accounts_provisioned=sum(1 for a in batch.accounts if a.is_new),
        needs_category_count=sum(1 for r in batch.rows if r.needs_review),
    )


@router.post("/upload", response_model=StagingBatchOut)
async def upload_statement(file: UploadFile = File(...), password: str | None = Form(default=None)):
    if get_store().current() is not None:
        raise _error(
            409, "STAGING_BATCH_EXISTS", "Commit or discard the pending statement before uploading another."
        )
    if not (file.filename or "").lower().endswith(".pdf"):
        raise _error(422, "UNPARSEABLE_STATEMENT_FORMAT", "Only PDF e-statements are supported.")

    data = await file.read()

    try:
        pdf = open_pdf(data, password)
    except EncryptedPdfError:
        raise _error(422, "ENCRYPTED_PDF_PASSWORD_REQUIRED", "This PDF is password-protected.")
    except IncorrectPasswordError:
        raise _error(422, "INCORRECT_PDF_PASSWORD", "The supplied password did not unlock this PDF.")

    try:
        try:
            parsed = detect_and_parse(pdf.pages)
        except UnparseableStatementError as exc:
            raise _error(422, "UNPARSEABLE_STATEMENT_FORMAT", str(exc))
    finally:
        pdf.close()

    with get_conn() as conn:
        rules = _fetch_active_rules(conn)
        contact_identifiers = _fetch_contact_identifiers(conn)

        staging_accounts: list[StagingAccount] = []
        staging_rows: list[StagingRow] = []
        row_index = 0

        for parsed_account in parsed.accounts:
            account_id = derive_account_id(parsed_account.bank_name, parsed_account.account_number)
            existing = conn.execute("SELECT 1 FROM accounts WHERE id = ?", (account_id,)).fetchone()
            staging_accounts.append(
                StagingAccount(
                    bank_name=parsed_account.bank_name,
                    account_number=parsed_account.account_number,
                    account_number_masked=parsed_account.account_number_masked,
                    account_type=parsed_account.account_type,
                    is_new=existing is None,
                )
            )

            seq_indices = compute_daily_sequence_indices(parsed_account.transactions)
            for tx, seq in zip(parsed_account.transactions, seq_indices):
                cleaned = clean_description(tx.raw_description)
                fingerprint = compute_fingerprint(account_id, tx.transaction_date, tx.amount, cleaned, seq)
                is_duplicate = (
                    conn.execute("SELECT 1 FROM transactions WHERE fingerprint = ?", (fingerprint,)).fetchone()
                    is not None
                )
                cat = categorize(tx.raw_description, rules, contact_identifiers)
                staging_rows.append(
                    StagingRow(
                        index=row_index,
                        account_number=parsed_account.account_number,
                        transaction_date=tx.transaction_date,
                        raw_description=tx.raw_description,
                        matched_label=cat.matched_label,
                        amount=tx.amount,
                        fingerprint=fingerprint,
                        category=cat.category,
                        subcategory=cat.subcategory,
                        is_excluded=cat.is_excluded,
                        exclusion_reason=cat.exclusion_reason,
                        contact_id=cat.contact_id,
                        needs_review=cat.needs_review,
                        is_duplicate=is_duplicate,
                    )
                )
                row_index += 1

    batch = StagingBatch(
        source_filename=file.filename or "statement.pdf",
        bank_name=parsed.bank_name,
        accounts=staging_accounts,
        rows=staging_rows,
    )
    get_store().create(batch)
    return _batch_to_response(batch)


@router.get("/staging/current", response_model=StagingBatchOut)
def get_current_staging_batch():
    batch = get_store().current()
    if batch is None:
        raise _error(404, "NO_STAGING_BATCH", "No statement is currently staged.")
    return _batch_to_response(batch)


@router.get("/staging/{batch_id}", response_model=StagingBatchOut)
def get_staging_batch(batch_id: str):
    try:
        batch = get_store().get(batch_id)
    except KeyError:
        raise _error(404, "STAGING_BATCH_NOT_FOUND", "No staging batch with that id.")
    return _batch_to_response(batch)


@router.patch("/staging/{batch_id}/rows/{index}", response_model=StagingBatchOut)
def update_staging_row(batch_id: str, index: int, body: StagingRowUpdateRequest):
    store = get_store()
    try:
        batch = store.get(batch_id)
    except KeyError:
        raise _error(404, "STAGING_BATCH_NOT_FOUND", "No staging batch with that id.")

    try:
        row = store.update_row(
            batch_id,
            index,
            category=body.category,
            subcategory=body.subcategory,
            needs_review=False,
        )
    except KeyError:
        raise _error(404, "STAGING_ROW_NOT_FOUND", "No staging row at that index.")

    with get_conn() as conn:
        if body.save_as_rule:
            pattern = body.rule_pattern or extract_display_name(row.raw_description)
            priority = body.rule_priority
            if priority is None:
                max_priority = conn.execute("SELECT MAX(priority) FROM rules WHERE is_default = 0").fetchone()[0]
                priority = (max_priority or 0) + 1
            conn.execute(
                "INSERT INTO rules (priority, match_pattern, target_category, target_subcategory, "
                "is_exclusion_rule) VALUES (?, ?, ?, ?, 0)",
                (priority, pattern, body.category, body.subcategory),
            )

        if body.save_as_contact:
            identifier = body.contact_identifier or extract_display_name(row.raw_description)
            name = body.contact_name or identifier
            existing_contact = conn.execute(
                "SELECT contact_id FROM contact_identifiers WHERE identifier = ?", (identifier,)
            ).fetchone()
            if existing_contact:
                contact_id = existing_contact["contact_id"]
            else:
                cur = conn.execute(
                    "INSERT INTO contacts (name, default_category, default_subcategory) VALUES (?, ?, ?)",
                    (name, body.category, body.subcategory),
                )
                contact_id = cur.lastrowid
                conn.execute(
                    "INSERT INTO contact_identifiers (contact_id, identifier) VALUES (?, ?)",
                    (contact_id, identifier),
                )
            store.update_row(batch_id, index, contact_id=contact_id)

    return _batch_to_response(batch)


@router.post("/staging/{batch_id}/commit", response_model=CommitResult)
def commit_staging_batch(batch_id: str):
    store = get_store()
    try:
        batch = store.get(batch_id)
    except KeyError:
        raise _error(404, "STAGING_BATCH_NOT_FOUND", "No staging batch with that id.")

    accounts_provisioned = 0
    transactions_committed = 0
    duplicates_skipped = 0
    refund_pairs_created = 0

    with get_conn() as conn:
        account_id_by_number: dict[str, str] = {}
        for acc in batch.accounts:
            account_id = derive_account_id(acc.bank_name, acc.account_number)
            account_id_by_number[acc.account_number] = account_id
            if acc.is_new:
                conn.execute(
                    "INSERT OR IGNORE INTO accounts (id, bank_name, account_number_masked, account_type) "
                    "VALUES (?, ?, ?, ?)",
                    (account_id, acc.bank_name, acc.account_number_masked, acc.account_type),
                )
                accounts_provisioned += 1

        touched_account_ids: set[str] = set()
        for row in batch.rows:
            if row.is_duplicate:
                duplicates_skipped += 1
                continue
            account_id = account_id_by_number[row.account_number]
            conn.execute(
                "INSERT INTO transactions (fingerprint, account_id, transaction_date, raw_description, "
                "cleaned_description, matched_label, amount, category, subcategory, contact_id, is_excluded, "
                "exclusion_reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row.fingerprint,
                    account_id,
                    row.transaction_date,
                    row.raw_description,
                    clean_description(row.raw_description),
                    row.matched_label,
                    row.amount,
                    row.category,
                    row.subcategory,
                    row.contact_id,
                    row.is_excluded,
                    row.exclusion_reason,
                ),
            )
            transactions_committed += 1
            touched_account_ids.add(account_id)

        for account_id in touched_account_ids:
            all_tx = conn.execute(
                "SELECT id, transaction_date, amount, raw_description FROM transactions WHERE account_id = ?",
                (account_id,),
            ).fetchall()
            paired_ids = set()
            for r in conn.execute(
                """
                SELECT original_transaction_id, refund_transaction_id FROM refund_pairings
                WHERE original_transaction_id IN (SELECT id FROM transactions WHERE account_id = ?)
                """,
                (account_id,),
            ).fetchall():
                paired_ids.add(r["original_transaction_id"])
                paired_ids.add(r["refund_transaction_id"])

            new_pairs = find_refund_pairs(all_tx, already_paired_ids=frozenset(paired_ids))
            for original_id, refund_id in new_pairs:
                conn.execute(
                    "INSERT INTO refund_pairings (original_transaction_id, refund_transaction_id) VALUES (?, ?)",
                    (original_id, refund_id),
                )
                refund_pairs_created += 1

    store.delete(batch_id)
    return CommitResult(
        transactions_committed=transactions_committed,
        duplicates_skipped=duplicates_skipped,
        accounts_provisioned=accounts_provisioned,
        refund_pairs_created=refund_pairs_created,
    )


@router.delete("/staging/{batch_id}", status_code=204)
def discard_staging_batch(batch_id: str):
    get_store().delete(batch_id)
