"""Regression tests for the DBS and OCBC parsers, against the synthetic
fixtures in `PDF Examples (Sanitized)/{DBS,OCBC}/`.

Read `scripts/generate_dbs_ocbc_samples.py`'s module docstring for what these
fixtures can and can't prove: they were drawn from the same understanding of
the layout the parsers were written from, so they show the parsers work on
that layout - they do not show that layout is what DBS and OCBC actually
print. The reconciliation tests below are the part that would survive being
pointed at a real statement, which is why the parsers refuse to return figures
that don't reconcile at all (see `parsing/columnar.py`).
"""

import glob
import io
import os
import re

import pdfplumber
import pytest

from app.parsing.columnar import StatementReconciliationError
from app.parsing.dbs import DBSParser
from app.parsing.ocbc import OCBCParser
from app.parsing.registry import detect_and_parse

DBS_DIR = "../PDF Examples (Sanitized)/DBS"
OCBC_DIR = "../PDF Examples (Sanitized)/OCBC"


def _parse(path: str):
    with pdfplumber.open(path) as pdf:
        return detect_and_parse(pdf.pages)


def _printed_totals(path: str) -> dict[str, float]:
    """The withdrawal/deposit figures the statement prints on its own `Total`
    row. Checking the parser against these rather than against numbers copied
    out of the generator is what stops the two drifting together."""
    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    totals = []
    for line in text.splitlines():
        if line.strip().startswith("Total"):
            amounts = [float(a.replace(",", "")) for a in re.findall(r"[\d,]+\.\d{2}", line)]
            if len(amounts) >= 2:
                totals.append({"withdrawals": amounts[0], "deposits": amounts[1]})
    assert totals, f"{path} prints no Total row to reconcile against"
    return {
        "withdrawals": round(sum(t["withdrawals"] for t in totals), 2),
        "deposits": round(sum(t["deposits"] for t in totals), 2),
    }


# --- DBS ------------------------------------------------------------------


def test_dbs_account_statement_parses_and_identifies_the_account():
    result = _parse(f"{DBS_DIR}/Account Statements/SampleAccountStatement_Mar2024.pdf")
    assert result.bank_name == "DBS"
    (acc,) = result.accounts
    assert acc.account_type == "DBS Multiplier Account"
    assert acc.account_number == "123-456789-0"
    assert acc.account_number_masked == "••7890"
    assert acc.is_card is False
    assert len(acc.transactions) == 10

    # The year comes from "Details as at 31 Mar 2024" - rows print no year.
    assert acc.transactions[0].transaction_date == "2024-03-01"
    assert acc.transactions[0].amount == 3200.00


def test_dbs_account_statement_excludes_table_furniture():
    result = _parse(f"{DBS_DIR}/Account Statements/SampleAccountStatement_Mar2024.pdf")
    for txn in result.accounts[0].transactions:
        assert "Balance Brought Forward" not in txn.raw_description
        assert "Balance Carried Forward" not in txn.raw_description
        assert not txn.raw_description.startswith("Total")


def test_dbs_account_statement_keeps_wrapped_descriptions_whole():
    """A PayNow line wraps onto a second row with the date column empty. The
    payee's name lands on that second row, and the categorization engine can't
    match a contact it never sees."""
    result = _parse(f"{DBS_DIR}/Account Statements/SampleAccountStatement_Mar2024.pdf")
    descriptions = [t.raw_description for t in result.accounts[0].transactions]
    payout = next(d for d in descriptions if "SAMPLE HOUSEMATE" in d)
    assert payout.startswith("FAST Payment / Receipt")
    assert payout.endswith("PayNow Transfer Other")


def test_dbs_consolidated_statement_splits_two_accounts_on_one_page():
    """DBS's default eStatement lists every account you hold, one section
    after another - often several on a single page. Reading only the first
    table would pour the second account's rows into the first."""
    result = _parse(f"{DBS_DIR}/Account Statements/SampleConsolidatedStatement_May2024.pdf")
    assert len(result.accounts) == 2

    by_number = {a.account_number: a for a in result.accounts}
    multiplier = by_number["123-456789-0"]
    savings = by_number["987-654321-0"]

    assert multiplier.account_type == "DBS Multiplier Account"
    assert savings.account_type == "POSB Savings Account"
    assert len(multiplier.transactions) == 3
    assert len(savings.transactions) == 3

    # The 200.00 PayNow credit belongs to the savings account, not the first one.
    assert any(t.amount == 200.00 for t in savings.transactions)
    assert all(t.amount != 200.00 for t in multiplier.transactions)


def test_dbs_card_statement_reads_credits_and_charges():
    result = _parse(f"{DBS_DIR}/Card Statements/SampleCardStatement_Mar2024.pdf")
    (acc,) = result.accounts
    assert acc.is_card is True
    assert acc.account_type == "DBS SAMPLE CARD"
    assert acc.account_number == "0000-1111-2222-3333"

    # A CR-suffixed amount is money coming back (the bill payment); everything
    # else on a card statement is a charge.
    assert acc.transactions[0].amount == 312.45
    assert all(t.amount < 0 for t in acc.transactions[1:])
    for txn in acc.transactions:
        assert "PREVIOUS BALANCE" not in txn.raw_description
        assert "NEW BALANCE" not in txn.raw_description


def test_dbs_card_statement_resolves_december_charges_to_the_previous_year():
    """A January statement's December rows are last year's. Nothing on the row
    itself says so - only the statement date does."""
    result = _parse(f"{DBS_DIR}/Card Statements/SampleCardStatement_Jan2025.pdf")
    dates = {t.raw_description: t.transaction_date for t in result.accounts[0].transactions}
    assert dates["TAKASHIMAYA"] == "2024-12-20"
    assert dates["FAIRPRICE XTRA"] == "2025-01-03"


# --- OCBC -----------------------------------------------------------------


def test_ocbc_account_statement_parses_past_the_value_date_column():
    """OCBC prints a second date column that DBS doesn't. It must not be read
    as the transaction date, nor shift the description column."""
    result = _parse(f"{OCBC_DIR}/Account Statements/SampleAccountStatement_Mar2024.pdf")
    assert result.bank_name == "OCBC"
    (acc,) = result.accounts
    assert acc.account_type == "OCBC 360 Account"
    assert acc.account_number == "501-234567-001"
    assert len(acc.transactions) == 8

    nets = next(t for t in acc.transactions if "HAINANESE" in t.raw_description)
    assert nets.raw_description == "NETS QR PURCHASE HAINANESE CHICKEN RICE"
    assert nets.amount == -6.70
    assert nets.transaction_date == "2024-03-03"


def test_ocbc_account_statement_excludes_balance_bf_and_cf():
    result = _parse(f"{OCBC_DIR}/Account Statements/SampleAccountStatement_Apr2024.pdf")
    for txn in result.accounts[0].transactions:
        assert "BALANCE B/F" not in txn.raw_description
        assert "BALANCE C/F" not in txn.raw_description


def test_ocbc_card_statement_reads_numeric_year_less_dates():
    """OCBC card rows date as "02/03", not DBS and UOB's "05 MAR"."""
    result = _parse(f"{OCBC_DIR}/Card Statements/SampleCardStatement_Mar2024.pdf")
    (acc,) = result.accounts
    assert acc.is_card is True
    assert acc.account_number == "0000-4444-5555-6666"
    assert len(acc.transactions) == 5

    dates = {t.raw_description: t.transaction_date for t in acc.transactions}
    assert dates["NTUC FAIRPRICE SINGAPORE SG"] == "2024-03-01"
    assert dates["FOODIE EXPRESS SINGAPORE SG"] == "2024-02-20"
    for txn in acc.transactions:
        assert "LAST MONTH" not in txn.raw_description.upper()


# --- the reconciliation guard itself --------------------------------------


def test_a_statement_whose_rows_do_not_match_its_printed_total_is_refused():
    """The parsers were built without a real statement to test against, so the
    failure that matters is a column boundary landing slightly wrong and
    dropping or misreading amounts - which produces a plausible import with
    wrong numbers. This is the check that turns that into a refusal."""
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(36, 800, "DBS Bank Ltd")
    c.drawString(36, 780, "Statement of Account")
    c.drawString(36, 760, "Details as at 31 Mar 2024")
    c.drawString(36, 730, "DBS Multiplier Account")
    c.drawString(36, 715, "Account No. 123-456789-0")
    c.drawString(50, 690, "DATE")
    c.drawString(145, 690, "DESCRIPTION")
    c.drawRightString(405, 690, "WITHDRAWAL")
    c.drawRightString(478, 690, "DEPOSIT")
    c.drawRightString(550, 690, "BALANCE")
    c.drawString(50, 670, "03 Mar")
    c.drawString(145, 670, "SAMPLE MERCHANT")
    c.drawRightString(405, 670, "10.00")
    c.drawRightString(550, 670, "990.00")
    c.drawString(145, 650, "Total")
    # The statement claims 99.00 of withdrawals; only 10.00 is on the table.
    c.drawRightString(405, 650, "99.00")
    c.drawRightString(478, 650, "0.00")
    c.save()

    with pytest.raises(StatementReconciliationError) as excinfo:
        with pdfplumber.open(io.BytesIO(buf.getvalue())) as pdf:
            detect_and_parse(pdf.pages)
    assert "did not reconcile" in str(excinfo.value)
    assert "99.00" in str(excinfo.value)


def test_a_second_table_without_its_own_heading_does_not_swallow_the_first():
    """`_section_end` finds the next section's heading by searching backwards
    from its header. When there is no heading between the two tables, that
    search runs past the header and lands on the *first* section's - which,
    unguarded, makes the first section's row range empty and drops it whole."""
    from app.parsing.columnar import _section_end
    from app.parsing.dbs.account_statement import SPEC

    class _Line:
        def __init__(self, text):
            self._text = text

        def text(self):
            return self._text

    lines = [
        _Line("DBS Multiplier Account"),
        _Line("Account No. 123-456789-0"),  # the only identity line
        _Line("DATE DESCRIPTION WITHDRAWAL DEPOSIT BALANCE"),  # header at 2
        _Line("03 Mar SAMPLE MERCHANT 10.00 990.00"),
        _Line("DATE DESCRIPTION WITHDRAWAL DEPOSIT BALANCE"),  # header at 4
        _Line("05 Mar OTHER MERCHANT 20.00 970.00"),
    ]
    headers = [(2, []), (4, [])]
    assert _section_end(lines, headers, 0, SPEC) == 4


def test_dbs_and_ocbc_parsers_report_themselves_as_implemented():
    assert DBSParser().parsing_implemented is True
    assert OCBCParser().parsing_implemented is True


# --- every fixture in the folders, not just the hand-picked ones ----------
# The tests above pin specific values. These walk whatever is actually in the
# folders, so a month added to the generator later is covered the day it
# lands instead of only when someone remembers to write a test for it.

ACCOUNT_STATEMENTS = sorted(glob.glob(f"{DBS_DIR}/Account Statements/*.pdf") + glob.glob(f"{OCBC_DIR}/Account Statements/*.pdf"))
CARD_STATEMENTS = sorted(glob.glob(f"{DBS_DIR}/Card Statements/*.pdf") + glob.glob(f"{OCBC_DIR}/Card Statements/*.pdf"))


@pytest.mark.parametrize("path", ACCOUNT_STATEMENTS, ids=lambda p: os.path.basename(p))
def test_every_account_statement_reconciles_against_its_own_printed_total(path):
    result = _parse(path)
    assert result.accounts
    transactions = [t for acc in result.accounts for t in acc.transactions]
    assert transactions, "a statement with no parsed transactions is a parser failure, not an empty month"

    printed = _printed_totals(path)
    withdrawals = round(sum(-t.amount for t in transactions if t.amount < 0), 2)
    deposits = round(sum(t.amount for t in transactions if t.amount > 0), 2)
    assert withdrawals == printed["withdrawals"]
    assert deposits == printed["deposits"]


@pytest.mark.parametrize("path", CARD_STATEMENTS, ids=lambda p: os.path.basename(p))
def test_every_card_statement_parses_a_card_with_transactions(path):
    result = _parse(path)
    assert result.accounts
    for acc in result.accounts:
        assert acc.is_card is True
        assert acc.transactions
        assert acc.account_number.startswith("0000-")  # placeholder card numbers only
