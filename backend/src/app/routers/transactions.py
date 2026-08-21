import sqlite3

from fastapi import APIRouter, HTTPException, Query

from app.db import get_conn
from app.models import RefundPairingOut, TransactionOut, TransactionUpdateRequest

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


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


@router.patch("/{transaction_id}", response_model=TransactionOut)
def update_transaction(transaction_id: int, body: TransactionUpdateRequest):
    with get_conn() as conn:
        existing = conn.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,)).fetchone()
        if existing is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "TRANSACTION_NOT_FOUND", "message": "No transaction with that id."},
            )

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
            raise HTTPException(
                status_code=404,
                detail={"code": "NO_REFUND_PAIRING", "message": "This transaction has no refund pairing."},
            )
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
