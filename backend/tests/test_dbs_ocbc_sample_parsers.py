"""Regression tests for the DBS and OCBC parsers, against the fixtures in
`PDF Examples (Sanitized)/{DBS,OCBC}/`.

Two kinds of fixture live there now:

* **Sanitized from real statements** - `scripts/sanitize_statement.py` rebuilt
  each PDF keeping the geometry, the bank's own wording and the figures, and
  replacing every name, address, account number and counterparty with its
  shape. They prove the parser reads the layout the bank actually prints. DBS's
  `SampleConsolidatedStatement_{Dec2023,Nov2024}.pdf` and OCBC's
  `Card Statements/SampleCardStatement_{Jul,Aug}2026.pdf` are these.
* Everything else is **synthetic**, drawn by `scripts/generate_dbs_ocbc_samples.py`.
  OCBC's deposit-account fixture is still layout-only - no real sample yet - so
  it only shows the parser works on the layout it was written from. The DBS
  synthetic fixtures, and the OCBC card parser, were rebuilt to the real layout
  once real statements arrived.

The reconciliation tests are the ones that would survive being pointed at any
real statement, which is why the parsers refuse to return figures that don't
reconcile against a total the statement prints for itself (`parsing/columnar.py`).
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
    """A PayNow line wraps onto a second row with the date column empty. A
    parser that stopped at the first row would return half a description and
    call it complete, which is indistinguishable from a correct parse until
    someone reads the output."""
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


def test_dbs_real_consolidated_statement_parses_and_reconciles():
    """`SampleConsolidatedStatement_{Dec2023,Nov2024}.pdf` are sanitized from
    real DBS consolidated eStatements (see the module docstring). They cover
    what the synthetic fixtures cannot: a statement spanning several pages, a
    per-page `Balance Brought/Carried Forward SGD` pair that is not a
    transaction, a dormant SRS section with an empty table, and the real
    `Total Balance Carried Forward in SGD:` row the reconciliation reads."""
    result = _parse(f"{DBS_DIR}/Account Statements/SampleConsolidatedStatement_Dec2023.pdf")
    assert result.bank_name == "DBS"
    (acc,) = result.accounts  # the empty SRS section is dropped
    assert acc.account_type == "DBS Multiplier Account"
    assert acc.is_card is False
    assert len(acc.transactions) == 50

    # Real transaction rows carry the year ("01/12/2023"), so it is read
    # straight off the row rather than resolved from the statement date.
    assert acc.transactions[0].transaction_date == "2023-12-01"
    assert acc.transactions[-1].transaction_date == "2023-12-31"

    withdrawals = round(sum(-t.amount for t in acc.transactions if t.amount < 0), 2)
    deposits = round(sum(t.amount for t in acc.transactions if t.amount > 0), 2)
    assert (withdrawals, deposits) == (1851.78, 2554.86)
    assert acc.transactions[-1].balance == 5264.65

    nov = _parse(f"{DBS_DIR}/Account Statements/SampleConsolidatedStatement_Nov2024.pdf")
    (nov_acc,) = nov.accounts
    assert len(nov_acc.transactions) == 38
    assert nov_acc.transactions[-1].balance == 8500.38


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
    result = _parse(f"{OCBC_DIR}/Account Statements/SampleAccountStatement_Mar2024.pdf")
    for txn in result.accounts[0].transactions:
        assert "BALANCE B/F" not in txn.raw_description
        assert "BALANCE C/F" not in txn.raw_description


OCBC_CARD_DIR = f"{OCBC_DIR}/Card Statements"


@pytest.fixture
def _ocbc_card_today(monkeypatch):
    """The OCBC card fixtures are sanitized from real statements whose summary
    box - the only place the statement date is printed - the contributor
    redacted. The parser falls back to resolving each year-less date against
    today, so the test pins today to just after the August statement."""
    import datetime as _dt

    monkeypatch.setattr("app.parsing.columnar._today", lambda: _dt.date(2026, 9, 4))


def test_ocbc_card_statement_reads_the_real_layout(_ocbc_card_today):
    """Real OCBC card layout: the card heading sits below the table header,
    dates are numeric and year-less ("19/06"), and a credit is bracketed
    rather than "CR"-suffixed."""
    result = _parse(f"{OCBC_CARD_DIR}/SampleCardStatement_Jul2026.pdf")
    assert result.bank_name == "OCBC"
    (acc,) = result.accounts
    assert acc.is_card is True
    assert acc.account_type == "OCBC INFINITY CASHBACK"
    assert acc.account_number_masked == "••3009"
    assert len(acc.transactions) == 44

    payment = acc.transactions[0]
    assert payment.raw_description.startswith("PAYMENT BY")
    assert payment.amount == 1133.96  # bracketed on the statement -> money in
    assert payment.transaction_date == "2026-07-05"

    assert acc.transactions[1].transaction_date == "2026-06-19"  # "19/06", resolved to 2026
    assert min(t.amount for t in acc.transactions) == -1004.00  # the biggest single charge

    for txn in acc.transactions:
        assert "LAST MONTH" not in txn.raw_description.upper()
        assert not txn.raw_description.upper().startswith("SUBTOTAL")

    # The `CCY CONVERSION FEE` / `FOR: 20.98 SGD` two-line row is kept whole.
    ccy = next(t for t in acc.transactions if t.raw_description.endswith("FOR: 20.98 SGD"))
    assert ccy.amount == -0.21


def test_ocbc_card_statement_reconciles_against_last_months_balance(_ocbc_card_today):
    """The parse only returns because opening balance + charges - credits
    equalled the SUBTOTAL each statement prints (`columnar._reconcile`); these
    pin the sums that satisfied it."""
    for name, opening, charges, credits, subtotal in [
        ("SampleCardStatement_Jul2026.pdf", 1133.96, 1530.39, 1146.46, 1517.89),
        ("SampleCardStatement_Aug2026.pdf", 1517.89, 4659.54, 1603.99, 4573.44),
    ]:
        (acc,) = _parse(f"{OCBC_CARD_DIR}/{name}").accounts
        out = round(sum(-t.amount for t in acc.transactions if t.amount < 0), 2)
        into = round(sum(t.amount for t in acc.transactions if t.amount > 0), 2)
        assert (out, into) == (charges, credits)
        assert round(opening + out - into, 2) == subtotal


def test_ocbc_card_identity_survives_a_redacted_card_number(_ocbc_card_today):
    """July prints the full card number, August has it redacted out. Both must
    resolve to the same account, so the key is the card product name, not the
    number."""
    jul = _parse(f"{OCBC_CARD_DIR}/SampleCardStatement_Jul2026.pdf").accounts[0]
    aug = _parse(f"{OCBC_CARD_DIR}/SampleCardStatement_Aug2026.pdf").accounts[0]
    assert jul.account_number == aug.account_number == "OCBC INFINITY CASHBACK"
    assert jul.account_number_masked == "••3009"
    assert aug.account_number_masked == "••••"


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
    c.drawString(50, 690, "Date")
    c.drawString(145, 690, "Description")
    c.drawRightString(405, 690, "Withdrawal (-)")
    c.drawRightString(478, 690, "Deposit (+)")
    c.drawRightString(550, 690, "Balance")
    c.drawString(50, 670, "03/03/2024")
    c.drawString(145, 670, "SAMPLE MERCHANT")
    c.drawRightString(405, 670, "10.00")
    c.drawRightString(550, 670, "990.00")
    c.drawString(145, 650, "Total Balance Carried Forward in SGD:")
    # The statement claims 99.00 of withdrawals; only 10.00 is on the table.
    c.drawRightString(405, 650, "99.00")
    c.drawRightString(478, 650, "0.00")
    c.drawRightString(550, 650, "990.00")
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
        # No real name or number: a synthetic fixture's card number is a
        # "0000-" placeholder, a sanitized real one keys on the card product.
        assert acc.account_number.startswith("0000-") or "OCBC" in acc.account_number
