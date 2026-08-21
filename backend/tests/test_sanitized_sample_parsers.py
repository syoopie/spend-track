"""Regression tests against the committed synthetic sample statements in
`PDF Examples (Sanitized)/`. Unlike `PDF Examples/` (real statements,
gitignored - see test_uob_account_parser.py / test_uob_card_parser.py),
these fixtures are safe to commit and always available, so this suite runs
on every clone without needing real bank statements.
"""

import pdfplumber
import pytest

from app.engine.refunds import find_refund_pairs
from app.parsing.uob import account_statement as astmt
from app.parsing.uob import card_statement as cstmt

SAMPLE_DIR = "../PDF Examples (Sanitized)/UOB"


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
