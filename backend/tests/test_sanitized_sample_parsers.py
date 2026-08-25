"""Regression tests against the committed synthetic sample statements in
`PDF Examples (Sanitized)/`. Unlike `PDF Examples/` (real statements,
gitignored - see test_uob_account_parser.py / test_uob_card_parser.py),
these fixtures are safe to commit and always available, so this suite runs
on every clone without needing real bank statements.
"""

import glob
import os
import re

import pdfplumber
import pytest

from app.engine.refunds import find_refund_pairs
from app.parsing.uob import account_statement as astmt
from app.parsing.uob import card_statement as cstmt

SAMPLE_DIR = "../PDF Examples (Sanitized)/UOB"


def _printed_totals(path: str) -> dict[str, float]:
    """The withdrawals/deposits figures the statement itself prints on its
    `Total` row - the parser's own output is checked against these rather
    than against numbers copied out of the generator, so the two can't drift
    together."""
    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    line = next(ln for ln in text.splitlines() if ln.strip().startswith("Total"))
    amounts = [float(a.replace(",", "")) for a in re.findall(r"[\d,]+\.\d{2}", line)]
    return {"withdrawals": amounts[0], "deposits": amounts[1]}


def _parse_account(filename):
    with pdfplumber.open(f"{SAMPLE_DIR}/Account Statements/{filename}") as pdf:
        return astmt.parse(pdf.pages)


def _parse_card(filename):
    with pdfplumber.open(f"{SAMPLE_DIR}/Card Statements/{filename}") as pdf:
        return cstmt.parse(pdf.pages)


def test_account_statement_parses_all_transactions_and_reconciles():
    result = _parse_account("SampleAccountStatement_Feb2024.pdf")
    acc = result.accounts[0]
    assert acc.account_number == "000-111-222-3"
    assert acc.account_number_masked == "••2223"
    assert len(acc.transactions) == 11

    withdrawals = round(sum(-t.amount for t in acc.transactions if t.amount < 0), 2)
    deposits = round(sum(t.amount for t in acc.transactions if t.amount > 0), 2)
    assert withdrawals == 407.60
    assert deposits == 3251.05
    assert acc.transactions[-1].balance == 7843.45

    for t in acc.transactions:
        assert "BALANCE B/F" not in t.raw_description
        assert not t.raw_description.startswith("Total")


def test_second_account_statement_continues_the_same_account():
    """Different month, same account number - exercises the account-id
    resolution path that lets duplicate detection work across statements."""
    result = _parse_account("SampleAccountStatement_Mar2024.pdf")
    acc = result.accounts[0]
    assert acc.account_number == "000-111-222-3"
    assert len(acc.transactions) == 6
    assert acc.transactions[-1].balance == 10827.77


def test_account_statement_refund_pairing_finds_the_planted_pair():
    result = _parse_account("SampleAccountStatement_Feb2024.pdf")
    acc = result.accounts[0]
    rows = [
        {"id": i, "transaction_date": t.transaction_date, "amount": t.amount, "raw_description": t.raw_description}
        for i, t in enumerate(acc.transactions)
    ]
    pairs = find_refund_pairs(rows)
    assert len(pairs) == 1
    original, refund = pairs[0]
    assert rows[original]["raw_description"] == "SAMPLE ONLINE STORE"
    assert rows[refund]["raw_description"] == "SAMPLE ONLINE STORE REFUND"


def test_card_statement_single_card_parses_correctly():
    result = _parse_card("SampleCardStatement_Feb2024.pdf")
    assert len(result.accounts) == 1
    acc = result.accounts[0]
    assert acc.account_type == "UOB SAMPLE CARD"
    assert acc.account_number == "0000-1111-2222-3333"
    assert len(acc.transactions) == 6
    # PAYMT THRU E-BANK is a credit (payment), everything else is a charge
    assert acc.transactions[0].amount == 150.00
    assert all(t.amount < 0 for t in acc.transactions[1:])


def test_jan_account_statement_chains_into_febs_fixed_opening_balance():
    """Jan's opening balance is solved backwards (see
    _opening_balance_for_closing in the generator) so this statement's
    closing balance lands exactly on Feb's hardcoded opening_balance=5000.00,
    making the two-month history continuous."""
    result = _parse_account("SampleAccountStatement_Jan2024.pdf")
    acc = result.accounts[0]
    assert len(acc.transactions) == 12
    assert acc.transactions[-1].balance == 5000.00


def test_apr_may_jun_account_statements_parse_with_expected_transaction_counts():
    for filename, count in [
        ("SampleAccountStatement_Apr2024.pdf", 12),
        ("SampleAccountStatement_May2024.pdf", 13),
        ("SampleAccountStatement_Jun2024.pdf", 12),
    ]:
        result = _parse_account(filename)
        acc = result.accounts[0]
        assert len(acc.transactions) == count, filename


def test_apr_statement_carries_insurance_and_investing_default_rule_bait():
    """These lines exist to exercise the Bills & Fees insurance rule and the
    Investing PayNow rule from engine/default_rules.py end to end."""
    result = _parse_account("SampleAccountStatement_Apr2024.pdf")
    descriptions = " ".join(t.raw_description for t in result.accounts[0].transactions)
    assert "Income Insurance" in descriptions
    assert "INTERACTIVE BR SG" in descriptions


def test_jan_and_apr_card_statements_parse_correctly():
    jan = _parse_card("SampleCardStatement_Jan2024.pdf")
    assert len(jan.accounts[0].transactions) == 6

    apr = _parse_card("SampleCardStatement_Apr2024.pdf")
    assert len(apr.accounts[0].transactions) == 6
    assert apr.accounts[0].transactions[0].amount == 180.00


def test_card_statement_multi_card_attributes_transactions_to_the_right_card():
    """No real UOB sample had more than one card - this fixture exists
    specifically to exercise that path (see engine/naming.py backward-search
    fix for the Summary-table false-positive)."""
    result = _parse_card("SampleCardStatement_MultiCard_Mar2024.pdf")
    assert len(result.accounts) == 2

    by_number = {acc.account_number: acc for acc in result.accounts}
    card1 = by_number["0000-1111-2222-3333"]
    card2 = by_number["0000-4444-5555-6666"]

    assert card1.account_type == "UOB SAMPLE CARD"
    assert len(card1.transactions) == 3
    assert all(t.amount < 0 for t in card1.transactions)

    assert card2.account_type == "UOB SAMPLE TRAVEL CARD"
    assert len(card2.transactions) == 3
    assert card2.transactions[1].amount == 200.00  # the PAYMT THRU E-BANK credit


# --- every month in the folder, not just the hand-picked fixtures ---------
# The tests above pin specific values in the Jan-Jun statements. These two
# walk whatever is actually in the folder, so a month added to the generator
# later (for a fuller demo dataset, say) is covered the day it lands instead
# of only when someone remembers to write a test for it.

ACCOUNT_STATEMENTS = sorted(glob.glob(f"{SAMPLE_DIR}/Account Statements/*.pdf"))
CARD_STATEMENTS = sorted(glob.glob(f"{SAMPLE_DIR}/Card Statements/*.pdf"))


@pytest.mark.parametrize("path", ACCOUNT_STATEMENTS, ids=lambda p: os.path.basename(p))
def test_every_account_statement_reconciles_against_its_own_printed_total(path):
    with pdfplumber.open(path) as pdf:
        result = astmt.parse(pdf.pages)
    acc = result.accounts[0]
    assert acc.transactions, "a statement with no parsed transactions is a parser failure, not an empty month"

    printed = _printed_totals(path)
    withdrawals = round(sum(-t.amount for t in acc.transactions if t.amount < 0), 2)
    deposits = round(sum(t.amount for t in acc.transactions if t.amount > 0), 2)
    assert withdrawals == printed["withdrawals"]
    assert deposits == printed["deposits"]


@pytest.mark.parametrize("path", CARD_STATEMENTS, ids=lambda p: os.path.basename(p))
def test_every_card_statement_parses_at_least_one_card_with_transactions(path):
    with pdfplumber.open(path) as pdf:
        result = cstmt.parse(pdf.pages)
    assert result.accounts
    for acc in result.accounts:
        assert acc.transactions
        assert acc.account_number.startswith("0000-")  # placeholder card numbers only
