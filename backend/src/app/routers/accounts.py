from fastapi import APIRouter

from app.db import get_conn
from app.errors import api_error
from app.models import AccountOut

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

_LIST_QUERY = """
    SELECT a.*, COUNT(t.id) AS transaction_count
    FROM accounts a LEFT JOIN transactions t ON t.account_id = a.id
    GROUP BY a.id
    ORDER BY a.created_at
"""


@router.get("", response_model=list[AccountOut])
def list_accounts():
    with get_conn() as conn:
        return [AccountOut(**dict(r)) for r in conn.execute(_LIST_QUERY).fetchall()]


@router.delete("/{account_id}", status_code=204)
def delete_account(account_id: str):
    """Deleting a statement clears its transactions but leaves the account
    row (a zero-transaction account is a valid state - see
    data_lifecycle.delete_all_transactions). This is the manual cleanup for
    one that is genuinely finished with. The zero-transaction guard is
    enforced here rather than left to schema.sql's ON DELETE CASCADE,
    because cascading would delete the transactions instead of refusing."""
    with get_conn() as conn:
        if conn.execute("SELECT 1 FROM accounts WHERE id = ?", (account_id,)).fetchone() is None:
            raise api_error(404, "ACCOUNT_NOT_FOUND", "No account with that id.")
        count = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE account_id = ?", (account_id,)
        ).fetchone()[0]
        if count > 0:
            raise api_error(
                409,
                "ACCOUNT_HAS_TRANSACTIONS",
                f"This account still has {count} transaction{'' if count == 1 else 's'}. "
                "Delete the statements it came from first.",
            )
        conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
