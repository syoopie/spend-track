import shutil
from pathlib import Path

from fastapi import APIRouter

from app.config import get_db_path, set_db_path
from app.db import get_conn, init_db
from app.errors import api_error
from app.localization import ACTIVE_COUNTRY
from app.models import DeleteScopeResult, RelocateRequest, ResetRequest, SettingsOut

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _schema_version(db_path: Path) -> int:
    with get_conn() as conn:
        return conn.execute("PRAGMA user_version").fetchone()[0]


def _require_delete_confirmation(body: ResetRequest) -> None:
    if body.confirm != "DELETE":
        raise api_error(400, "RESET_CONFIRMATION_MISMATCH", "Type DELETE to confirm.")


def _localization_fields() -> dict:
    return {
        "country_code": ACTIVE_COUNTRY.code,
        "country_name": ACTIVE_COUNTRY.name,
        "currency_code": ACTIVE_COUNTRY.currency_code,
        "currency_symbol": ACTIVE_COUNTRY.currency_symbol,
        "transfer_scheme_name": ACTIVE_COUNTRY.transfer_scheme_name,
        "supported_banks": [p.bank_name for p in ACTIVE_COUNTRY.bank_parsers],
    }


@router.get("", response_model=SettingsOut)
def get_settings():
    db_path = get_db_path()
    size = db_path.stat().st_size if db_path.exists() else 0
    return SettingsOut(
        db_path=str(db_path),
        size_bytes=size,
        schema_version=_schema_version(db_path),
        **_localization_fields(),
    )


@router.post("/relocate", response_model=SettingsOut)
def relocate_database(body: RelocateRequest):
    """Per TECHNICAL_SPEC.md §6: checkpoint + copy data.db(-wal/-shm) to the
    new location, remove the old files, then repoint config.json."""
    old_path = get_db_path()
    if not old_path.exists():
        raise api_error(404, "DB_NOT_FOUND", "No database file to relocate.")

    new_path = Path(body.new_path)
    if new_path.resolve() == old_path.resolve():
        raise api_error(400, "RELOCATE_SAME_PATH", "New path is the same as the current database path.")
    new_path.parent.mkdir(parents=True, exist_ok=True)

    with get_conn() as conn:
        conn.execute("PRAGMA wal_checkpoint(FULL)")

    for suffix in ("", "-wal", "-shm"):
        src = Path(str(old_path) + suffix)
        if src.exists():
            shutil.copy2(src, Path(str(new_path) + suffix))
    for suffix in ("", "-wal", "-shm"):
        src = Path(str(old_path) + suffix)
        if src.exists():
            src.unlink()

    set_db_path(new_path)

    size = new_path.stat().st_size if new_path.exists() else 0
    return SettingsOut(
        db_path=str(new_path),
        size_bytes=size,
        schema_version=_schema_version(new_path),
        **_localization_fields(),
    )


@router.post("/reset", status_code=204)
def reset_database(body: ResetRequest):
    _require_delete_confirmation(body)
    db_path = get_db_path()
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(db_path) + suffix)
        if p.exists():
            p.unlink()
    init_db(db_path)


@router.post("/delete-rules", response_model=DeleteScopeResult)
def delete_all_rules(body: ResetRequest):
    """Only user-created rules - is_default rules are a pure function of
    default_rules.py and get reconciled back on the next startup anyway, so
    deleting them here would be a no-op that misleads the user about what
    just happened."""
    _require_delete_confirmation(body)
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM rules WHERE is_default = 0")
        return DeleteScopeResult(deleted_count=cur.rowcount)


@router.post("/delete-contacts", response_model=DeleteScopeResult)
def delete_all_contacts(body: ResetRequest):
    _require_delete_confirmation(body)
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM contacts")
        return DeleteScopeResult(deleted_count=cur.rowcount)


@router.post("/delete-transactions", response_model=DeleteScopeResult)
def delete_all_transactions(body: ResetRequest):
    """Accounts are left in place - an account with zero transactions is a
    valid, unremarkable state (e.g. right after this action, or before the
    first statement for it is ever uploaded)."""
    _require_delete_confirmation(body)
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM transactions")
        return DeleteScopeResult(deleted_count=cur.rowcount)
