import io

import pypdf
import pytest
from fastapi.testclient import TestClient

ACCOUNT_SAMPLE = "../PDF Examples/UOB/Account Statements/eStatement_29072.23852206947.pdf"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SG_TRACKER_DB_PATH", str(tmp_path / "test.db"))
    from app.main import app

    with TestClient(app) as c:
        yield c


def _upload(client, path=ACCOUNT_SAMPLE, password=None):
    with open(path, "rb") as f:
        data = {"password": password} if password else {}
        return client.post(
            "/api/statements/upload",
            files={"file": ("statement.pdf", f, "application/pdf")},
            data=data,
        )


def test_upload_parses_and_stages(client):
    resp = _upload(client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["bank_name"] == "UOB"
    assert body["new_extracted"] == 39
    assert body["duplicates_skipped"] == 0
    assert body["new_accounts_provisioned"] == 1
    assert body["accounts"][0]["account_number_masked"] == "••5678"
    assert len(body["rows"]) == 39
    # PayNow rows with no matching rule/contact should be flagged for review
    assert body["needs_category_count"] > 0


def test_upload_rejects_non_pdf(client):
    resp = client.post(
        "/api/statements/upload",
        files={"file": ("statement.csv", io.BytesIO(b"date,desc,amount"), "text/csv")},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "UNPARSEABLE_STATEMENT_FORMAT"


def test_upload_rejects_unrecognized_pdf(client):
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    resp = client.post(
        "/api/statements/upload",
        files={"file": ("statement.pdf", buf, "application/pdf")},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "UNPARSEABLE_STATEMENT_FORMAT"


def test_upload_requires_password_for_encrypted_pdf(client):
    with open(ACCOUNT_SAMPLE, "rb") as f:
        reader = pypdf.PdfReader(f)
        writer = pypdf.PdfWriter()
        for p in reader.pages:
            writer.add_page(p)
        writer.encrypt(user_password="secret123")
        buf = io.BytesIO()
        writer.write(buf)
    buf.seek(0)
    resp = client.post(
        "/api/statements/upload",
        files={"file": ("statement.pdf", buf, "application/pdf")},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "ENCRYPTED_PDF_PASSWORD_REQUIRED"


def test_patch_row_assigns_category_and_creates_rule_and_contact(client):
    body = _upload(client).json()
    batch_id = body["batch_id"]
    review_row = next(r for r in body["rows"] if r["needs_review"])

    resp = client.patch(
        f"/api/statements/staging/{batch_id}/rows/{review_row['index']}",
        json={
            "category": "PayNow Transfers",
            "save_as_rule": True,
            "save_as_contact": True,
            "contact_name": "Boon Heng",
            "contact_identifier": "BOON HENG",
        },
    )
    assert resp.status_code == 200
    updated_row = next(r for r in resp.json()["rows"] if r["index"] == review_row["index"])
    assert updated_row["category"] == "PayNow Transfers"
    assert updated_row["needs_review"] is False
    assert updated_row["contact_id"] is not None


def test_commit_persists_transactions_and_provisions_account(client):
    body = _upload(client).json()
    batch_id = body["batch_id"]

    resp = client.post(f"/api/statements/staging/{batch_id}/commit")
    assert resp.status_code == 200
    result = resp.json()
    assert result["transactions_committed"] == 39
    assert result["accounts_provisioned"] == 1
    assert result["duplicates_skipped"] == 0

    # staging batch should be gone
    assert client.get(f"/api/statements/staging/{batch_id}").status_code == 404


def test_reuploading_committed_statement_shows_all_duplicates(client):
    first = _upload(client).json()
    client.post(f"/api/statements/staging/{first['batch_id']}/commit")

    second = _upload(client).json()
    assert second["new_extracted"] == 0
    assert second["duplicates_skipped"] == 39


def test_discard_batch_removes_it(client):
    body = _upload(client).json()
    batch_id = body["batch_id"]
    assert client.delete(f"/api/statements/staging/{batch_id}").status_code == 204
    assert client.get(f"/api/statements/staging/{batch_id}").status_code == 404
