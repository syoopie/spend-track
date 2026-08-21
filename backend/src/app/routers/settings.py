import shutil
from pathlib import Path

from fastapi import APIRouter

from app.config import get_db_path, set_db_path
from app.db import get_conn, init_db
from app.errors import api_error
from app.models import RelocateRequest, ResetRequest, SettingsOut

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _schema_version(db_path: Path) -> int:
    with get_conn() as conn:
        return conn.execute("PRAGMA user_version").fetchone()[0]


@router.get("", response_model=SettingsOut)
def get_settings():
    db_path = get_db_path()
    size = db_path.stat().st_size if db_path.exists() else 0
    return SettingsOut(db_path=str(db_path), size_bytes=size, schema_version=_schema_version(db_path))


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
    return SettingsOut(db_path=str(new_path), size_bytes=size, schema_version=_schema_version(new_path))


@router.post("/reset", status_code=204)
def reset_database(body: ResetRequest):
    if body.confirm != "DELETE":
        raise api_error(400, "RESET_CONFIRMATION_MISMATCH", "Type DELETE to confirm.")
    db_path = get_db_path()
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(db_path) + suffix)
        if p.exists():
            p.unlink()
    init_db(db_path)
