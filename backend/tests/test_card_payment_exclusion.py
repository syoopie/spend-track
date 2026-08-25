"""Both halves of a credit card bill payment, end to end through the API.

The same payment appears twice when you track both statements: as an outflow
on the bank account that paid it, and as a credit on the card it settled.
Neither is spending and neither is income - counting either one distorts a
year of totals. `engine/card_payments.py` detects both; this covers them
against the committed sanitized samples, so the behaviour is verified on a
fresh clone rather than only on a machine that happens to have real
statements in the gitignored `PDF Examples/` folder.
"""

import pytest
from fastapi.testclient import TestClient

ACCOUNT = "../PDF Examples (Sanitized)/UOB/Account Statements/SampleAccountStatement_Feb2024.pdf"
CARD = "../PDF Examples (Sanitized)/UOB/Card Statements/SampleCardStatement_Feb2024.pdf"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SG_TRACKER_DB_PATH", str(tmp_path / "test.db"))
    from app.main import app

    with TestClient(app) as c:
        yield c


def _upload(client, *paths):
    handles = [open(p, "rb") for p in paths]
    try:
        files = [("files", (f"statement{i}.pdf", h, "application/pdf")) for i, h in enumerate(handles)]
        return client.post("/api/statements/upload", files=files)
    finally:
        for h in handles:
            h.close()


def _rows_matching(body, needle):
    return [r for r in body["rows"] if needle in r["raw_description"]]


def test_both_halves_excluded_when_the_whole_statement_pair_is_uploaded(client):
    body = _upload(client, ACCOUNT, CARD).json()

    bank_side = _rows_matching(body, "mBK-UOB Cards")
    assert len(bank_side) == 1
    assert bank_side[0]["amount"] < 0
    assert bank_side[0]["is_excluded"] is True
    assert "already counted" in bank_side[0]["exclusion_reason"]

    card_side = _rows_matching(body, "PAYMT THRU")
    assert len(card_side) == 1
    assert card_side[0]["amount"] > 0
    assert card_side[0]["is_excluded"] is True
    assert "not income" in card_side[0]["exclusion_reason"]


def test_card_payment_credit_is_excluded_even_with_no_bank_statement(client):
    """Unlike the bank-side half, this one isn't gated on having seen the
    paying account - a payment credit posting to a card settles that card
    either way."""
    body = _upload(client, CARD).json()
    card_side = _rows_matching(body, "PAYMT THRU")
    assert len(card_side) == 1
    assert card_side[0]["is_excluded"] is True


def test_the_cards_own_purchases_are_untouched(client):
    body = _upload(client, CARD).json()
    purchases = [r for r in body["rows"] if r["amount"] < 0]
    assert purchases
    assert all(r["is_excluded"] is False for r in purchases)


def test_excluded_payments_stay_out_of_committed_totals(client):
    """The dashboard reads committed transactions, so the exclusion has to
    survive the commit, not just the staging preview."""
    body = _upload(client, ACCOUNT, CARD).json()
    client.post(f"/api/statements/staging/{body['batch_id']}/commit")

    committed = client.get("/api/transactions", params={"include_excluded": True}).json()
    payments = [t for t in committed if "PAYMT THRU" in t["raw_description"]]
    assert payments and all(t["is_excluded"] for t in payments)

    inflow = sum(t["amount"] for t in committed if t["amount"] > 0 and not t["is_excluded"])
    payment_total = sum(t["amount"] for t in payments)
    assert payment_total > 0
    assert inflow == pytest.approx(
        sum(t["amount"] for t in committed if t["amount"] > 0) - payment_total
    )
