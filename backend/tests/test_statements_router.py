import glob
import io

import pypdf
import pytest
from fastapi.testclient import TestClient

# PDF Examples/ is an optional, gitignored local folder for testing against
# your own real statements - discovered by glob rather than a hardcoded
# filename so no real statement's filename ever ends up in tracked source,
# and skipped entirely when absent (a fresh clone has none) rather than
# failing. See test_uob_account_parser.py for the same pattern.
_ACCOUNT_SAMPLES = sorted(glob.glob("../PDF Examples/UOB/Account Statements/*.pdf"))
ACCOUNT_SAMPLE = _ACCOUNT_SAMPLES[0] if _ACCOUNT_SAMPLES else None

pytestmark = pytest.mark.skipif(
    ACCOUNT_SAMPLE is None, reason="No real UOB statements found locally (optional, gitignored PDF Examples/ folder)"
)


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
            files={"files": ("statement.pdf", f, "application/pdf")},
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
        files={"files": ("statement.csv", io.BytesIO(b"date,desc,amount"), "text/csv")},
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
        files={"files": ("statement.pdf", buf, "application/pdf")},
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
        files={"files": ("statement.pdf", buf, "application/pdf")},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "ENCRYPTED_PDF_PASSWORD_REQUIRED"


def test_patch_row_assigns_category_and_creates_rule_and_contact(client):
    body = _upload(client).json()
    batch_id = body["batch_id"]
    review_row = next(r for r in body["rows"] if r["needs_review"])

    resp = client.patch(
        f"/api/statements/staging/{batch_id}/rows/{review_row['key']}",
        json={
            "category": "Paynow",
            "save_as_rule": True,
            "save_as_contact": True,
            "contact_name": "Boon Heng",
            "contact_identifier": "BOON HENG",
        },
    )
    assert resp.status_code == 200
    updated_row = next(r for r in resp.json()["rows"] if r["key"] == review_row["key"])
    assert updated_row["category"] == "Paynow"
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


def test_current_staging_batch(client):
    assert client.get("/api/statements/staging/current").status_code == 404

    body = _upload(client).json()
    current = client.get("/api/statements/staging/current").json()
    assert current["batch_id"] == body["batch_id"]

    client.delete(f"/api/statements/staging/{body['batch_id']}")
    assert client.get("/api/statements/staging/current").status_code == 404


def test_upload_multiple_files_merges_into_one_batch(client):
    feb = "../PDF Examples (Sanitized)/UOB/Account Statements/SampleAccountStatement_Feb2024.pdf"
    mar = "../PDF Examples (Sanitized)/UOB/Account Statements/SampleAccountStatement_Mar2024.pdf"
    with open(feb, "rb") as f1, open(mar, "rb") as f2:
        resp = client.post(
            "/api/statements/upload",
            files=[
                ("files", ("feb.pdf", f1, "application/pdf")),
                ("files", ("mar.pdf", f2, "application/pdf")),
            ],
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source_filenames"] == ["feb.pdf", "mar.pdf"]
    # one shared account across both statements - not duplicated in the merged batch
    assert len(body["accounts"]) == 1
    assert body["duplicates_skipped"] == 0
    assert len(body["rows"]) == body["new_extracted"]

    commit_resp = client.post(f"/api/statements/staging/{body['batch_id']}/commit")
    assert commit_resp.status_code == 200
    assert commit_resp.json()["accounts_provisioned"] == 1
    assert commit_resp.json()["transactions_committed"] == body["new_extracted"]


def test_upload_multiple_files_aborts_batch_on_any_failure(client):
    feb = "../PDF Examples (Sanitized)/UOB/Account Statements/SampleAccountStatement_Feb2024.pdf"
    with open(feb, "rb") as f1:
        resp = client.post(
            "/api/statements/upload",
            files=[
                ("files", ("feb.pdf", f1, "application/pdf")),
                ("files", ("bad.csv", io.BytesIO(b"not a pdf"), "text/csv")),
            ],
        )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "UNPARSEABLE_STATEMENT_FORMAT"
    # no partial batch should have been staged
    assert client.get("/api/statements/staging/current").status_code == 404


def test_card_bill_payment_excluded_when_card_statement_uploaded_in_same_batch(client):
    """Uploading the account statement and the matching card statement
    together must not double-count the GIRO payment settling the card bill
    as spending on top of the card's own line-item purchases."""
    account = "../PDF Examples (Sanitized)/UOB/Account Statements/SampleAccountStatement_Feb2024.pdf"
    card = "../PDF Examples (Sanitized)/UOB/Card Statements/SampleCardStatement_Feb2024.pdf"
    with open(account, "rb") as f1, open(card, "rb") as f2:
        resp = client.post(
            "/api/statements/upload",
            files=[
                ("files", ("account.pdf", f1, "application/pdf")),
                ("files", ("card.pdf", f2, "application/pdf")),
            ],
        )
    assert resp.status_code == 200
    body = resp.json()
    bill_payment_rows = [r for r in body["rows"] if "mBK-UOB Cards" in r["raw_description"]]
    assert len(bill_payment_rows) == 1
    assert bill_payment_rows[0]["is_excluded"] is True
    assert "already counted" in bill_payment_rows[0]["exclusion_reason"]


def test_card_bill_payment_not_excluded_without_a_card_statement(client):
    """The same GIRO payment line, uploaded on its own (no card statement
    ever provided) - it must stay counted since it's the only record of
    that money leaving."""
    account = "../PDF Examples (Sanitized)/UOB/Account Statements/SampleAccountStatement_Feb2024.pdf"
    resp = _upload(client, path=account)
    body = resp.json()
    bill_payment_rows = [r for r in body["rows"] if "mBK-UOB Cards" in r["raw_description"]]
    assert len(bill_payment_rows) == 1
    assert bill_payment_rows[0]["is_excluded"] is False


def test_second_upload_rejected_while_one_is_pending(client):
    first = _upload(client).json()
    resp = _upload(client)
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "STAGING_BATCH_EXISTS"

    client.post(f"/api/statements/staging/{first['batch_id']}/commit")
    assert _upload(client).status_code == 200
