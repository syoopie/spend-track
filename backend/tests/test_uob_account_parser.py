import glob
import re

import pdfplumber
import pytest

from app.parsing.uob import account_statement as astmt

SAMPLE_DIR = "../PDF Examples/UOB/Account Statements"
SAMPLES = sorted(glob.glob(f"{SAMPLE_DIR}/*.pdf"))


@pytest.fixture(scope="module", params=SAMPLES, ids=[p.split("/")[-1] for p in SAMPLES])
def parsed(request):
    with pdfplumber.open(request.param) as pdf:
        return astmt.parse(pdf.pages), pdf


def _expected_totals(pdf):
    """Pull the statement's own printed Total row for cross-validation."""
    for page in pdf.pages:
        text = page.extract_text() or ""
        m = re.search(r"Total\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})", text)
        if m:
            return tuple(float(g.replace(",", "")) for g in m.groups())
    raise AssertionError("could not find Total row in sample fixture")


def test_account_identity(parsed):
    result, _ = parsed
    acc = result.accounts[0]
    assert acc.bank_name == "UOB"
    assert re.match(r"\d{3}-\d{3}-\d{3}-\d", acc.account_number)
    assert acc.account_number_masked == "••" + re.sub(r"\D", "", acc.account_number)[-4:]


def test_no_balance_bf_or_total_rows_leak_through(parsed):
    result, _ = parsed
    for t in result.accounts[0].transactions:
        assert "BALANCE B/F" not in t.raw_description
        assert not t.raw_description.strip().startswith("Total")


def test_no_footer_contamination(parsed):
    result, _ = parsed
    for t in result.accounts[0].transactions:
        assert "relation thereto" not in t.raw_description
        assert "Raffles Place" not in t.raw_description
        assert "UOB Plaza" not in t.raw_description


def test_totals_match_statement(parsed):
    result, pdf = parsed
    acc = result.accounts[0]
    expected_withdrawals, expected_deposits, expected_balance = _expected_totals(pdf)

    withdrawals = round(sum(-t.amount for t in acc.transactions if t.amount < 0), 2)
    deposits = round(sum(t.amount for t in acc.transactions if t.amount > 0), 2)

    assert withdrawals == expected_withdrawals
    assert deposits == expected_deposits
    assert acc.transactions[-1].balance == expected_balance
