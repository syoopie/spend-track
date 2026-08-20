from fastapi import APIRouter

from app.db import get_conn
from app.models import AccountOut

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
def list_accounts():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM accounts ORDER BY created_at").fetchall()
        return [AccountOut(**dict(r)) for r in rows]
