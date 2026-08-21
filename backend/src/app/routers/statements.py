from fastapi import APIRouter, File, Form, UploadFile

from app import repo
from app.db import get_conn
from app.engine.fingerprint import clean_description, compute_daily_sequence_indices, compute_fingerprint
from app.engine.identity import derive_account_id
from app.engine.naming import extract_display_name
from app.engine.refunds import find_refund_pairs
from app.engine.rules import categorize
from app.engine.staging_store import StagingAccount, StagingBatch, StagingRow, get_store
from app.errors import api_error
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
        source_filenames=batch.source_filenames,
        bank_name=batch.bank_name,
        accounts=[
            StagingAccountOut(
                bank_name=a.bank_name,
                account_number_masked=a.account_number_masked,
                account_type=a.account_type,
                is_new=a.is_new,
                is_card=a.is_card,
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
async def upload_statement(files: list[UploadFile] = File(...), password: str | None = Form(default=None)):
    if get_store().current() is not None:
        raise api_error(
            409, "STAGING_BATCH_EXISTS", "Commit or discard the pending statement before uploading another."
        )
    if not files:
        raise api_error(422, "UNPARSEABLE_STATEMENT_FORMAT", "No files were provided.")
    for f in files:
        if not (f.filename or "").lower().endswith(".pdf"):
            raise api_error(422, "UNPARSEABLE_STATEMENT_FORMAT", f"'{f.filename}' is not a PDF e-statement.")

    # Parse every file up front, before touching the DB/staging store, so a
    # failure partway through (bad password, unparseable format) leaves no
    # partial batch behind - the whole multi-file upload is all-or-nothing.
    parsed_files = []
    for f in files:
        data = await f.read()
        filename = f.filename or "statement.pdf"
        try:
            pdf = open_pdf(data, password)
        except EncryptedPdfError:
            raise api_error(422, "ENCRYPTED_PDF_PASSWORD_REQUIRED", f"'{filename}' is password-protected.")
        except IncorrectPasswordError:
            raise api_error(422, "INCORRECT_PDF_PASSWORD", f"The supplied password did not unlock '{filename}'.")
        try:
            try:
                parsed = detect_and_parse(pdf.pages)
            except UnparseableStatementError as exc:
                raise api_error(422, "UNPARSEABLE_STATEMENT_FORMAT", f"'{filename}': {exc}")
        finally:
            pdf.close()
        parsed_files.append((filename, parsed))

    with get_conn() as conn:
        rules = repo.fetch_active_rules(conn)
        contact_identifiers = repo.fetch_contact_identifiers(conn)
        category_directions = repo.fetch_category_directions(conn)
        # Any card account already committed, or parsed anywhere in this same
        # multi-file batch, is enough to treat a "pay my card bill" line on a
        # bank account as already counted elsewhere - see engine/card_payments.py.
        has_card_account = (
            conn.execute("SELECT 1 FROM accounts WHERE is_card = 1 LIMIT 1").fetchone() is not None
            or any(pa.is_card for _f, parsed in parsed_files for pa in parsed.accounts)
        )

        staging_accounts: list[StagingAccount] = []
        account_ids_by_key: dict[tuple[str, str], str] = {}  # (bank_name, account_number) -> account_id
        staging_rows: list[StagingRow] = []
        seen_fingerprints: set[str] = set()
        row_index = 0

        for _filename, parsed in parsed_files:
            for parsed_account in parsed.accounts:
                key = (parsed_account.bank_name, parsed_account.account_number)
                if key not in account_ids_by_key:
                    account_id = derive_account_id(parsed_account.bank_name, parsed_account.account_number)
                    account_ids_by_key[key] = account_id
                    existing = conn.execute("SELECT 1 FROM accounts WHERE id = ?", (account_id,)).fetchone()
                    staging_accounts.append(
                        StagingAccount(
                            bank_name=parsed_account.bank_name,
                            account_number=parsed_account.account_number,
                            account_number_masked=parsed_account.account_number_masked,
                            account_type=parsed_account.account_type,
                            is_new=existing is None,
                            is_card=parsed_account.is_card,
                        )
                    )
                account_id = account_ids_by_key[key]

                seq_indices = compute_daily_sequence_indices(parsed_account.transactions)
                for tx, seq in zip(parsed_account.transactions, seq_indices):
                    cleaned = clean_description(tx.raw_description)
                    fingerprint = compute_fingerprint(account_id, tx.transaction_date, tx.amount, cleaned, seq)
                    is_duplicate = fingerprint in seen_fingerprints or (
                        conn.execute("SELECT 1 FROM transactions WHERE fingerprint = ?", (fingerprint,)).fetchone()
                        is not None
                    )
                    seen_fingerprints.add(fingerprint)
                    cat = categorize(
                        tx.raw_description,
                        rules,
                        contact_identifiers,
                        amount=tx.amount,
                        category_directions=category_directions,
                        has_card_account=has_card_account,
                        posting_account_is_card=parsed_account.is_card,
                    )
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

    bank_names = {parsed.bank_name for _filename, parsed in parsed_files}
    batch = StagingBatch(
        source_filenames=[filename for filename, _parsed in parsed_files],
        bank_name=bank_names.pop() if len(bank_names) == 1 else " + ".join(sorted(bank_names)),
        accounts=staging_accounts,
        rows=staging_rows,
    )
    try:
        get_store().create(batch)
    except ValueError:
        # A second upload can race past the current()-is-None check above
        # while this one was busy parsing PDFs - StagingStore.create() is the
        # actual point of truth, so translate its rejection into the same
        # clean 409 the upfront check gives the common (non-racing) case.
        raise api_error(
            409, "STAGING_BATCH_EXISTS", "Commit or discard the pending statement before uploading another."
        )
    return _batch_to_response(batch)


@router.get("/staging/current", response_model=StagingBatchOut)
def get_current_staging_batch():
    batch = get_store().current()
    if batch is None:
        raise api_error(404, "NO_STAGING_BATCH", "No statement is currently staged.")
    return _batch_to_response(batch)


@router.get("/staging/{batch_id}", response_model=StagingBatchOut)
def get_staging_batch(batch_id: str):
    try:
        batch = get_store().get(batch_id)
    except KeyError:
        raise api_error(404, "STAGING_BATCH_NOT_FOUND", "No staging batch with that id.")
    return _batch_to_response(batch)


@router.patch("/staging/{batch_id}/rows/{index}", response_model=StagingBatchOut)
def update_staging_row(batch_id: str, index: int, body: StagingRowUpdateRequest):
    store = get_store()
    try:
        batch = store.get(batch_id)
    except KeyError:
        raise api_error(404, "STAGING_BATCH_NOT_FOUND", "No staging batch with that id.")

    try:
        row = store.update_row(
            batch_id,
            index,
            category=body.category,
            subcategory=body.subcategory,
            needs_review=False,
        )
    except KeyError:
        raise api_error(404, "STAGING_ROW_NOT_FOUND", "No staging row at that index.")

    with get_conn() as conn:
        if body.save_as_rule:
            pattern = body.rule_pattern or extract_display_name(row.raw_description)
            priority = body.rule_priority if body.rule_priority is not None else repo.next_user_rule_priority(conn)
            repo.insert_rule(
                conn,
                priority=priority,
                match_pattern=pattern,
                target_category=body.category,
                target_subcategory=body.subcategory,
            )

        if body.save_as_contact:
            identifier = body.contact_identifier or extract_display_name(row.raw_description)
            name = body.contact_name or identifier
            contact_id = repo.find_contact_id_by_identifier(conn, identifier)
            if contact_id is None:
                contact_id = repo.insert_contact(
                    conn,
                    name=name,
                    default_category=body.category,
                    default_subcategory=body.subcategory,
                    identifiers=[identifier],
                )
            store.update_row(batch_id, index, contact_id=contact_id)

    return _batch_to_response(batch)


@router.post("/staging/{batch_id}/commit", response_model=CommitResult)
def commit_staging_batch(batch_id: str):
    store = get_store()
    try:
        batch = store.get(batch_id)
    except KeyError:
        raise api_error(404, "STAGING_BATCH_NOT_FOUND", "No staging batch with that id.")

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
                    "INSERT OR IGNORE INTO accounts (id, bank_name, account_number_masked, account_type, is_card) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (account_id, acc.bank_name, acc.account_number_masked, acc.account_type, acc.is_card),
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
