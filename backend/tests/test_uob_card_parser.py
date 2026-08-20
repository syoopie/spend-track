import glob
import re

import pdfplumber
import pytest

from app.parsing.uob import card_statement as cstmt

SAMPLE_DIR = "../PDF Examples/UOB/Card Statements"
SAMPLES = sorted(glob.glob(f"{SAMPLE_DIR}/*.pdf"))


@pytest.fixture(scope="module", params=SAMPLES, ids=[p.split("/")[-1] for p in SAMPLES])
def parsed(request):
    with pdfplumber.open(request.param) as pdf:
        result = cstmt.parse(pdf.pages)
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    return result, full_text


def test_card_identity(parsed):
    result, _ = parsed
    assert len(result.accounts) == 1
    acc = result.accounts[0]
    assert acc.bank_name == "UOB"
    assert acc.account_type == "UOB ONE CARD"
    assert re.match(r"\d{4}-\d{4}-\d{4}-\d{4}", acc.account_number)
    assert acc.account_number_masked == "••" + re.sub(r"\D", "", acc.account_number)[-4:]


def test_no_balance_or_total_rows_leak_through(parsed):
    result, _ = parsed
    for t in result.accounts[0].transactions:
        assert "PREVIOUS BALANCE" not in t.raw_description
        assert "SUB TOTAL" not in t.raw_description
        assert "TOTAL BALANCE FOR" not in t.raw_description


def test_no_footer_contamination(parsed):
    result, _ = parsed
    for t in result.accounts[0].transactions:
        assert "relation thereto" not in t.raw_description
        assert "Raffles Place" not in t.raw_description


def test_subtotal_reconciles_with_previous_balance(parsed):
    """UOB's printed SUB TOTAL is a running balance: PREVIOUS BALANCE + charges
    - credits. It is not simply this statement's net movement, so validation
    must account for the carried-forward balance too."""
    result, full_text = parsed
    acc = result.accounts[0]

    prev_m = re.search(r"PREVIOUS BALANCE\s+([\d,]+\.\d{2})", full_text)
    prev_balance = float(prev_m.group(1).replace(",", "")) if prev_m else 0.0
    sub_total_m = re.search(r"SUB TOTAL\s+([\d,]+\.\d{2})", full_text)
    assert sub_total_m, "could not find SUB TOTAL row in sample fixture"
    expected = float(sub_total_m.group(1).replace(",", ""))

    charges = sum(-t.amount for t in acc.transactions if t.amount < 0)
    credits = sum(t.amount for t in acc.transactions if t.amount > 0)
    assert round(prev_balance + charges - credits, 2) == expected


def test_dates_are_iso_and_sane(parsed):
    result, _ = parsed
    for t in result.accounts[0].transactions:
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", t.transaction_date)
