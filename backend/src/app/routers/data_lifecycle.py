"""Data lifecycle: Relocate, Nuclear Reset, and the three scoped deletes
(rules/contacts/transactions) - genuinely one concept (destructive actions on
the DB file itself), distinct from AI provider configuration and Appearance.
Its own top-level `/api/data-lifecycle` prefix (rather than nested under
`/api/settings/*`) reflects the module boundary in the route surface, not
just the file layout.
"""

import io
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import date
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import Response

from app.config import SECRET_CONFIG_KEYS, config_file_path, get_db_path, set_db_path
from app.db import get_conn, init_db
from app.errors import api_error
from app.models import DeleteScopeResult, PathCheckRequest, PathCheckResult, RelocateRequest, ResetRequest, SettingsOut
from app.routers.settings import build_settings_out

router = APIRouter(prefix="/api/data-lifecycle", tags=["data-lifecycle"])


def _require_delete_confirmation(body: ResetRequest) -> None:
    if body.confirm != "DELETE":
        raise api_error(400, "RESET_CONFIRMATION_MISMATCH", "Type DELETE to confirm.")


@router.post("/check-path", response_model=PathCheckResult)
def check_path(body: PathCheckRequest):
    """Validated on blur by the Relocate modal (SET-6) - the user used to type
    an absolute path from memory with no feedback until Migrate was clicked
    and it failed. Checks the *parent* directory (not the target file, which
    usually doesn't exist yet) is writable, and reports free space there."""
    raw = body.path.strip()
    if not raw:
        return PathCheckResult(valid=False, resolved_path="", free_bytes=None, error="Enter a path.")
    try:
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            return PathCheckResult(valid=False, resolved_path=str(candidate), free_bytes=None, error="Path must be absolute.")
        resolved = candidate.resolve()
        if resolved.exists() and resolved.is_dir():
            return PathCheckResult(
                valid=False, resolved_path=str(resolved), free_bytes=None, error="That's a directory - name a file, not a folder."
            )
        parent = resolved.parent
        if not parent.exists():
            return PathCheckResult(valid=False, resolved_path=str(resolved), free_bytes=None, error="Parent directory does not exist.")
        if not os.access(parent, os.W_OK):
            return PathCheckResult(valid=False, resolved_path=str(resolved), free_bytes=None, error="Directory is not writable.")
        free_bytes = shutil.disk_usage(parent).free
        return PathCheckResult(valid=True, resolved_path=str(resolved), free_bytes=free_bytes, error=None)
    except OSError as exc:
        return PathCheckResult(valid=False, resolved_path=raw, free_bytes=None, error=str(exc))


@router.post("/relocate", response_model=SettingsOut)
def relocate_database(body: RelocateRequest):
    """Per docs/technical-spec.md §6: checkpoint + copy data.db(-wal/-shm) to the
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
    return build_settings_out(new_path)


BACKUP_README = """SpendTrack backup
=================

Everything this app knows about your money, as of {today}.

  data.db       your accounts, transactions, categories, rules and contacts
  config.json   your settings (AI provider keys are NOT included - see below)

To restore, on this or another computer:

  1. Install SpendTrack and start it once, so it creates its folder.
  2. Quit it.
  3. Copy the two files above into that folder, replacing what's there.
     The folder is the one shown under Settings in the app; by default
     it is:
        Windows   C:\\Users\\<you>\\.spendtrack
        macOS     /Users/<you>/.spendtrack
        Linux     /home/<you>/.spendtrack
  4. Start it again.

Or, without copying anything: put data.db wherever you like and point the
app at it with Settings -> Change Database Path.

Not included, on purpose:

  * AI provider API keys. A backup tends to end up in cloud storage or an
    email attachment, and a key that leaks is a key someone else can spend.
    Re-enter yours under Settings after restoring.
  * Accent colour and other look-and-feel choices. Those live in your
    browser, not in the database, and cost one click to set again.

This file is plain SQLite. You can open data.db with any SQLite browser if
you ever want your data out of this app entirely.
"""


def _consistent_db_snapshot(db_path: Path) -> bytes:
    """A copy of the database taken through SQLite's own backup API.

    Reading the file off disk instead would be a gamble: SQLite writes a
    `-journal` sidecar mid-transaction, so a plain copy taken at the wrong
    moment is a database that needs recovery. The backup API serializes
    against writers and hands back a file that is consistent by
    construction - which matters here because the user is most likely to
    click Download right after an upload.
    """
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "data.db"
        source = sqlite3.connect(db_path)
        try:
            destination = sqlite3.connect(target)
            try:
                source.backup(destination)
            finally:
                destination.close()
        finally:
            source.close()
        return target.read_bytes()


def _config_without_secrets() -> str:
    """config.json with the API keys blanked - see BACKUP_README for why."""
    path = config_file_path()
    cfg = json.loads(path.read_text()) if path.exists() else {}
    for key in SECRET_CONFIG_KEYS:
        if cfg.get(key):
            cfg[key] = ""
    return json.dumps(cfg, indent=2)


@router.get("/export")
def export_backup():
    """One zip holding everything worth keeping, for a backup or a move to
    another machine. Built in memory: the database is a few MB at a year of
    statements, and a temp file would have to be cleaned up on a path that
    can fail midway."""
    db_path = get_db_path()
    if not db_path.exists():
        raise api_error(404, "DB_NOT_FOUND", "No database file to export yet - upload a statement first.")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("data.db", _consistent_db_snapshot(db_path))
        archive.writestr("config.json", _config_without_secrets())
        archive.writestr("README.txt", BACKUP_README.format(today=date.today().isoformat()))

    filename = f"spendtrack-backup-{date.today().isoformat()}.zip"
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
