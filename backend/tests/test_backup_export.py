"""The one-click backup: what goes in the zip, and what deliberately doesn't.

The point of this endpoint is that a non-technical user can get all their
data out in one click - so the failure that matters isn't a 500, it's a zip
that quietly omits something (leaving someone with a backup that can't
restore) or quietly includes an API key (leaving a secret in whatever cloud
folder the zip lands in).
"""

import io
import json
import sqlite3
import zipfile

import pytest
from fastapi.testclient import TestClient

ACCOUNT_SAMPLE = "../PDF Examples (Sanitized)/UOB/Account Statements/SampleAccountStatement_Feb2024.pdf"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SPENDTRACK_DB_PATH", str(tmp_path / "test.db"))
    from app.main import app

    with TestClient(app) as c:
        yield c


def _commit_a_statement(client):
    with open(ACCOUNT_SAMPLE, "rb") as f:
        body = client.post("/api/statements/upload", files={"files": ("s.pdf", f, "application/pdf")}).json()
    client.post(f"/api/statements/staging/{body['batch_id']}/commit")


def _download(client) -> zipfile.ZipFile:
    resp = client.get("/api/data-lifecycle/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert resp.headers["content-disposition"].startswith('attachment; filename="spendtrack-backup-')
    return zipfile.ZipFile(io.BytesIO(resp.content))


def test_the_zip_holds_the_database_the_settings_and_an_explanation(client):
    _commit_a_statement(client)
    archive = _download(client)
    assert sorted(archive.namelist()) == ["README.txt", "config.json", "data.db"]


def test_the_exported_database_opens_and_holds_the_same_rows(client, tmp_path):
    """A zip containing a corrupt or truncated database is worse than no
    backup at all, because it isn't noticed until it's needed."""
    _commit_a_statement(client)
    archive = _download(client)

    restored = tmp_path / "restored.db"
    restored.write_bytes(archive.read("data.db"))
    copy = sqlite3.connect(restored)
    live = sqlite3.connect(tmp_path / "test.db")

    assert copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    for table in ("transactions", "accounts", "rules", "categories", "contacts"):
        assert copy.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == (
            live.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        ), table
    assert copy.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] > 0


def test_api_keys_are_stripped_from_the_backup(client):
    """A backup ends up in cloud storage or an email attachment. The rest of
    the AI settings survive so a restore only costs re-entering the key."""
    resp = client.patch(
        "/api/ai",
        json={
            "ai_provider": "openai_compatible",
            "openai_model": "gpt-4o-mini",
            "openai_api_key": "sk-secret-value-12345",
            "anthropic_api_key": "sk-ant-secret-67890",
        },
    )
    assert resp.status_code == 200, resp.text
    _commit_a_statement(client)
    archive = _download(client)

    cfg = json.loads(archive.read("config.json"))
    assert cfg["openai_api_key"] == ""
    assert cfg["anthropic_api_key"] == ""
    assert cfg["openai_model"] == "gpt-4o-mini"
    assert cfg["ai_provider"] == "openai_compatible"

    whole_zip = b"".join(archive.read(name) for name in archive.namelist())
    for secret in (b"sk-secret-value-12345", b"sk-ant-secret-67890"):
        assert secret not in whole_zip


def test_the_readme_says_how_to_restore_and_what_is_missing(client):
    _commit_a_statement(client)
    readme = _download(client).read("README.txt").decode()
    assert "Change Database Path" in readme
    assert "API keys" in readme
    assert ".spendtrack" in readme


def test_export_before_any_data_exists_is_a_clear_error(client):
    """A brand new install has no database file yet - that's a 404 with a
    reason, not a zip holding nothing."""
    from app.config import get_db_path

    get_db_path().unlink(missing_ok=True)
    resp = client.get("/api/data-lifecycle/export")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "DB_NOT_FOUND"
