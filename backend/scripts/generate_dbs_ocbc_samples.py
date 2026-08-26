"""Generate synthetic DBS and OCBC sample statements for the public repo.

Why these are synthetic, and what that does and doesn't buy:

No bank publishes a specimen statement, and a real one carries a name, a home
address and an account number, so there was no DBS or OCBC PDF to build the
parsers against (see docs/adding-a-bank.md). What *is* public is the layout -
which columns each statement prints, under which headings, in which order,
with which not-a-transaction rows opening and closing the table. These
fixtures encode that layout, and they are drawn to be genuinely parseable, so
`tests/test_dbs_ocbc_sample_parsers.py` exercises the real parsers rather than
a mock.

What they cannot do is prove the parsers work on a real statement, because
they were drawn from the same understanding of the layout the parsers were
written from - if that understanding is wrong, fixture and parser are wrong
together. That gap is what `scripts/sanitize_statement.py` exists to close:
it turns a contributor's real statement into a shareable one that keeps the
layout and drops the PII. The two deliberate differences from the UOB
fixtures both come from this:

* Every column position here is drawn at a plausible-but-arbitrary x, because
  no real statement was measured. The parsers read their column ranges off
  the header row at parse time (`pdf_utils.columns_from_header`) rather than
  from hardcoded x-values, so this is not a number that has to be kept in
  sync with anything - which is the point.
* DBS's table furniture is drawn in upper case and OCBC's in proper case, as
  each bank prints it, so the fixtures cover both and the parsers' header
  matching stays case-insensitive on purpose.

Run with: uv run python scripts/generate_dbs_ocbc_samples.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from reportlab.pdfbase.pdfmetrics import stringWidth

from statement_canvas import FONT, FONT_BOLD, FOOTER_TOP_CUTOFF, Doc

OUT_ROOT = Path(__file__).resolve().parents[2] / "PDF Examples (Sanitized)"

SAMPLE_NAME = "SAMPLE CUSTOMER"
SAMPLE_ADDRESS = ["1 SAMPLE STREET", "#01-01 EXAMPLE BUILDING", "SINGAPORE 000000"]

LINE_H = 12.5
TABLE_TOP = 250.0
BODY_SIZE = 9


def wrap(text: str, max_width: float, size: float = BODY_SIZE) -> list[str]:
    """Break a description across as many physical lines as it needs.

    Real statements wrap a long PayNow or GIRO description onto continuation
    rows rather than letting it run under the amount columns, and the parsers
    rely on that: a word whose x lands past the description column's right
    edge is read as part of the next column. Wrapping here by measured text
    width (rather than a guessed character count) keeps the fixtures honest
    about that boundary instead of quietly overflowing it.
    """
    words = text.split()
    out: list[str] = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if line and stringWidth(candidate, FONT, size) > max_width:
            out.append(line)
            line = word
        else:
            line = candidate
    if line:
        out.append(line)
    return out or [""]


def _notice(bank: str) -> str:
    return (
        f"SAMPLE DATA - SYNTHETIC, NOT AN OFFICIAL {bank} DOCUMENT - "
        "all names, addresses and numbers below are fictional placeholders."
    )


def _footer(bank: str, legal_name: str) -> list[tuple[float, str]]:
    return [
        (800, _notice(bank)),
        (815, "Page {page}"),
        (828, f"{legal_name} (sample letterhead - synthetic document)"),
    ]


# --------------------------------------------------------------------------
# Deposit account statements (DBS and OCBC share a shape, differing in
# casing, in OCBC's extra value-date column, and in what the opening and
# closing rows are called)
# --------------------------------------------------------------------------


@dataclass
class Txn:
    """One transaction. `lines[1:]` are continuation lines - a wrapped PayNow
    or GIRO detail printed with the date column left empty, which is the case
    the parsers' description-accumulation branch exists for."""

    date: str  # "03 Mar"
    lines: list[str]
    withdrawal: float | None = None
    deposit: float | None = None
    balance: float = 0.0  # filled in by _apply_running_balance


@dataclass
class AccountSection:
    name: str
    number: str
    opening_balance: float
    txns: list[Txn]
    closing_balance: float = field(init=False, default=0.0)

    def __post_init__(self):
        self.closing_balance = _apply_running_balance(self.opening_balance, self.txns)

    @property
    def total_withdrawals(self) -> float:
        return round(sum(t.withdrawal or 0 for t in self.txns), 2)

    @property
    def total_deposits(self) -> float:
        return round(sum(t.deposit or 0 for t in self.txns), 2)


def _apply_running_balance(opening: float, txns: list[Txn]) -> float:
    """Compute each transaction's running balance, so whoever edits the
    transaction list below never has to keep a column of balances in sync by
    hand (and so the reconciliation check is testing the parser, not a typo)."""
    running = opening
    for txn in txns:
        running -= txn.withdrawal or 0
        running += txn.deposit or 0
        txn.balance = round(running, 2)
    return round(running, 2)


@dataclass(frozen=True)
class AccountLayout:
    """The bank-specific parts of a deposit-account statement."""

    bank: str
    legal_name: str
    heading: str  # the account-type wording, e.g. "DBS Multiplier Account"
    date_header: str
    value_date_header: str | None
    description_header: str
    withdrawal_header: str
    deposit_header: str
    balance_header: str
    opening_row: str
    closing_row: str
    totals_row: str
    date_x: float = 50.0
    value_date_x: float = 95.0
    description_x: float = 145.0
    withdrawal_right: float = 405.0
    deposit_right: float = 478.0
    balance_right: float = 550.0


DBS_ACCOUNT = AccountLayout(
    bank="DBS",
    legal_name="DBS Bank Ltd",
    heading="DBS Multiplier Account",
    date_header="DATE",
    value_date_header=None,
    description_header="DESCRIPTION",
    withdrawal_header="WITHDRAWAL",
    deposit_header="DEPOSIT",
    balance_header="BALANCE",
    opening_row="Balance Brought Forward",
    closing_row="Balance Carried Forward",
    totals_row="Total",
)

OCBC_ACCOUNT = AccountLayout(
    bank="OCBC",
    legal_name="Oversea-Chinese Banking Corporation Limited",
    heading="OCBC 360 Account",
    date_header="Date",
    value_date_header="Value Date",
    description_header="Description",
    withdrawal_header="Withdrawal",
    deposit_header="Deposit",
    balance_header="Balance",
    opening_row="BALANCE B/F",
    closing_row="BALANCE C/F",
    totals_row="Total",
)


def generate_account_statement(
    path: Path,
    layout: AccountLayout,
    statement_date: str,  # "31 Mar 2024"
    period_start: str,  # "01 Mar"
    sections: list[AccountSection],
):
    doc = Doc(path, _footer(layout.bank, layout.legal_name))
    # The description column ends where the withdrawal header begins - which
    # is exactly the boundary `pdf_utils.columns_from_header` derives - so
    # measure it the same way rather than guessing a safe-looking width.
    desc_width = (layout.withdrawal_right - stringWidth(layout.withdrawal_header, FONT_BOLD, BODY_SIZE)) - layout.description_x - 6

    # Page 1 header. None of this is parsed except the statement date, which
    # is where every transaction's year comes from - the rows themselves print
    # no year.
    doc.text(36, 40, layout.legal_name, size=10, font=FONT_BOLD)
    doc.text(36, 70, SAMPLE_NAME, size=10, font=FONT_BOLD)
    for i, line in enumerate(SAMPLE_ADDRESS):
        doc.text(36, 84 + i * 12, line)
    doc.text(36, 150, "Statement of Account", size=14, font=FONT_BOLD)
    doc.text(36, 170, f"Details as at {statement_date}")

    top = TABLE_TOP

    def draw_section_header(section: AccountSection, continued: bool) -> float:
        nonlocal top
        if top > FOOTER_TOP_CUTOFF - 60:
            doc.new_page()
            top = 60.0
        suffix = " (continued)" if continued else ""
        doc.text(36, top, f"{section.name}{suffix}", size=10, font=FONT_BOLD)
        top += 16
        doc.text(36, top, f"Account No. {section.number}")
        top += 16
        doc.text(36, top, "CURRENCY : SINGAPORE DOLLAR", size=8)
        top += 18
        doc.text(layout.date_x, top, layout.date_header, font=FONT_BOLD)
        if layout.value_date_header:
            doc.text(layout.value_date_x, top, layout.value_date_header, font=FONT_BOLD)
        doc.text(layout.description_x, top, layout.description_header, font=FONT_BOLD)
        doc.text_right(layout.withdrawal_right, top, layout.withdrawal_header, font=FONT_BOLD)
        doc.text_right(layout.deposit_right, top, layout.deposit_header, font=FONT_BOLD)
        doc.text_right(layout.balance_right, top, layout.balance_header, font=FONT_BOLD)
        top += 18
        return top

    for section in sections:
        draw_section_header(section, continued=False)

        doc.text(layout.date_x, top, period_start)
        doc.text(layout.description_x, top, layout.opening_row)
        doc.text_right(layout.balance_right, top, f"{section.opening_balance:,.2f}")
        top += LINE_H

        for txn in section.txns:
            if top > FOOTER_TOP_CUTOFF - 20:
                doc.new_page()
                top = 60.0
                draw_section_header(section, continued=True)
            wrapped = [w for line in txn.lines for w in wrap(line, desc_width)]
            doc.text(layout.date_x, top, txn.date)
            if layout.value_date_header:
                doc.text(layout.value_date_x, top, txn.date)
            doc.text(layout.description_x, top, wrapped[0])
            if txn.withdrawal is not None:
                doc.text_right(layout.withdrawal_right, top, f"{txn.withdrawal:,.2f}")
            if txn.deposit is not None:
                doc.text_right(layout.deposit_right, top, f"{txn.deposit:,.2f}")
            doc.text_right(layout.balance_right, top, f"{txn.balance:,.2f}")
            top += LINE_H
            for extra in wrapped[1:]:
                if top > FOOTER_TOP_CUTOFF - 20:
                    doc.new_page()
                    top = 60.0
                    draw_section_header(section, continued=True)
                doc.text(layout.description_x, top, extra)
                top += LINE_H

        if top > FOOTER_TOP_CUTOFF - 40:
            doc.new_page()
            top = 60.0
        doc.text(layout.description_x, top, layout.closing_row)
        doc.text_right(layout.balance_right, top, f"{section.closing_balance:,.2f}")
        top += LINE_H
        doc.text(layout.description_x, top, layout.totals_row)
        doc.text_right(layout.withdrawal_right, top, f"{section.total_withdrawals:,.2f}")
        doc.text_right(layout.deposit_right, top, f"{section.total_deposits:,.2f}")
        top += 34

    doc.save()
    return path


# --------------------------------------------------------------------------
# Credit card statements
# --------------------------------------------------------------------------


@dataclass
class CardTxn:
    date: str  # "05 MAR" for DBS, "05/03" for OCBC
    lines: list[str]
    amount: float  # negative = charge, positive = credit (drawn with a CR suffix)


@dataclass
class CardSection:
    name: str
    number: str
    previous_balance: float
    txns: list[CardTxn]
    new_balance: float = field(init=False, default=0.0)

    def __post_init__(self):
        # PREVIOUS BALANCE is a running balance carried in from last month, so
        # the closing figure is that plus this month's charges less its
        # credits - not just the net of the rows below it. Getting this wrong
        # is the trap CLAUDE.md records for UOB's SUB TOTAL.
        self.new_balance = round(self.previous_balance - sum(t.amount for t in self.txns), 2)


@dataclass(frozen=True)
class CardLayout:
    bank: str
    legal_name: str
    card_name: str
    date_header: list[str]  # drawn as consecutive words, e.g. ["TRANSACTION", "DATE"]
    description_header: str
    amount_header: str
    previous_balance_row: str
    new_balance_row: str
    date_x: float = 50.0
    description_x: float = 150.0
    amount_right: float = 545.0


DBS_CARD = CardLayout(
    bank="DBS",
    legal_name="DBS Bank Ltd",
    card_name="DBS SAMPLE CARD",
    date_header=["DATE"],
    description_header="DESCRIPTION",
    amount_header="AMOUNT (S$)",
    previous_balance_row="PREVIOUS BALANCE",
    new_balance_row="NEW BALANCE",
)

OCBC_CARD = CardLayout(
    bank="OCBC",
    legal_name="Oversea-Chinese Banking Corporation Limited",
    card_name="OCBC SAMPLE CARD",
    date_header=["TRANSACTION", "DATE"],
    description_header="DESCRIPTION",
    amount_header="AMOUNT (S$)",
    previous_balance_row="LAST MONTH'S BALANCE",
    new_balance_row="NEW BALANCE",
)


def generate_card_statement(
    path: Path,
    layout: CardLayout,
    statement_date: str,  # "15 MAR 2024" (DBS) or "15-03-2024" (OCBC)
    cards: list[CardSection],
):
    doc = Doc(path, _footer(layout.bank, layout.legal_name))
    desc_width = (layout.amount_right - stringWidth(layout.amount_header, FONT_BOLD, BODY_SIZE)) - layout.description_x - 6

    doc.text(36, 40, layout.legal_name, size=10, font=FONT_BOLD)
    doc.text(36, 60, "Credit Card Statement", size=13, font=FONT_BOLD)
    doc.text(36, 80, f"Statement Date {statement_date}")
    doc.text(36, 110, SAMPLE_NAME, size=10, font=FONT_BOLD)
    for i, line in enumerate(SAMPLE_ADDRESS):
        doc.text(36, 124 + i * 12, line)

    # A summary table listing each card, above the per-card tables. It repeats
    # the card number under a different heading, which is exactly the
    # false-positive the parsers avoid by searching *backwards* from a
    # confirmed table header for the identity line (see CLAUDE.md).
    doc.text(36, 180, "Card Summary", size=10, font=FONT_BOLD)
    summary_top = 198.0
    for card in cards:
        doc.text(36, summary_top, card.name)
        doc.text(240, summary_top, card.number)
        doc.text_right(520, summary_top, f"{card.new_balance:,.2f}")
        summary_top += 14

    top = summary_top + 34

    def draw_card_header(card: CardSection, continued: bool):
        nonlocal top
        if top > FOOTER_TOP_CUTOFF - 60:
            doc.new_page()
            top = 60.0
        doc.text(36, top, card.name, size=10, font=FONT_BOLD)
        top += 16
        suffix = " (continued)" if continued else ""
        doc.text(36, top, f"Card No. {card.number}{suffix}")
        top += 20
        x = layout.date_x
        for word in layout.date_header:
            doc.text(x, top, word, font=FONT_BOLD)
            # Advance by the word's measured width, not a fixed step: OCBC's
            # two-word "TRANSACTION DATE" heading overruns any step small
            # enough to look right for a one-word heading, and two header
            # words drawn on top of each other come back out of pdfplumber as
            # the single word "TRANSACTIONDATE", which matches nothing.
            x += stringWidth(word, FONT_BOLD, BODY_SIZE) + 5
        doc.text(layout.description_x, top, layout.description_header, font=FONT_BOLD)
        doc.text_right(layout.amount_right, top, layout.amount_header, font=FONT_BOLD)
        top += 18

    for card in cards:
        draw_card_header(card, continued=False)

        doc.text(layout.description_x, top, layout.previous_balance_row)
        doc.text_right(layout.amount_right, top, f"{card.previous_balance:,.2f}")
        top += LINE_H

        for txn in card.txns:
            if top > FOOTER_TOP_CUTOFF - 20:
                doc.new_page()
                top = 60.0
                draw_card_header(card, continued=True)
            wrapped = [w for line in txn.lines for w in wrap(line, desc_width)]
            doc.text(layout.date_x, top, txn.date)
            doc.text(layout.description_x, top, wrapped[0])
            amount_text = f"{txn.amount:,.2f} CR" if txn.amount > 0 else f"{-txn.amount:,.2f}"
            doc.text_right(layout.amount_right, top, amount_text)
            top += LINE_H
            for extra in wrapped[1:]:
                if top > FOOTER_TOP_CUTOFF - 20:
                    doc.new_page()
                    top = 60.0
                    draw_card_header(card, continued=True)
                doc.text(layout.description_x, top, extra)
                top += LINE_H

        if top > FOOTER_TOP_CUTOFF - 30:
            doc.new_page()
            top = 60.0
        doc.text(layout.description_x, top, layout.new_balance_row)
        doc.text_right(layout.amount_right, top, f"{card.new_balance:,.2f}")
        top += 34

    doc.save()
    return path


# --------------------------------------------------------------------------
# Row builders - the description wording each bank actually prints
# --------------------------------------------------------------------------
# Real DBS and OCBC descriptions are not free text: each transfer rail writes
# its own fixed preamble ("FAST Payment / Receipt", "FAST PAYMENT via
# PayNow-Mobile to ...") and the categorization engine keys off exactly those
# markers. Fixtures with invented wording would parse fine and still fail to
# exercise engine/paynow.py or the default rule bank, so these helpers keep to
# the real formats.


def dbs_paynow_out(date: str, payee: str, amount: float) -> Txn:
    return Txn(date, [f"FAST Payment / Receipt PayNow Transfer To: {payee}", "PayNow Transfer Other"], withdrawal=amount)


def dbs_paynow_in(date: str, payer: str, ref: str, amount: float) -> Txn:
    return Txn(date, [f"FAST Payment / Receipt Incoming PayNow Ref {ref}", f"From: {payer} Transfer Other"], deposit=amount)


def dbs_card_purchase(date: str, merchant: str, amount: float) -> Txn:
    return Txn(date, [f"Point-of-Sale Transaction {merchant}"], withdrawal=amount)


def dbs_giro(date: str, payee: str, amount: float) -> Txn:
    return Txn(date, [f"GIRO Payment {payee}"], withdrawal=amount)


def dbs_salary(date: str, amount: float) -> Txn:
    return Txn(date, ["GIRO Salary SAMPLE EMPLOYER PTE LTD"], deposit=amount)


def ocbc_paynow_out(date: str, payee: str, amount: float) -> Txn:
    return Txn(date, [f"FAST PAYMENT via PayNow-Mobile to {payee}", "OTHR - PayNow Transfer"], withdrawal=amount)


def ocbc_paynow_in(date: str, payer: str, amount: float) -> Txn:
    return Txn(date, [f"FAST PAYMENT RECEIVED via PayNow-Mobile from {payer}", "OTHR - OTHR"], deposit=amount)


def ocbc_nets(date: str, merchant: str, amount: float) -> Txn:
    return Txn(date, [f"NETS QR PURCHASE {merchant}"], withdrawal=amount)


def ocbc_giro(date: str, payee: str, amount: float) -> Txn:
    return Txn(date, [f"IBG GIRO {payee}"], withdrawal=amount)


def ocbc_salary(date: str, amount: float) -> Txn:
    return Txn(date, ["GIRO - SALARY SAMPLE EMPLOYER PTE LTD"], deposit=amount)


def charge(date: str, merchant: str, amount: float) -> CardTxn:
    return CardTxn(date, [merchant], amount=-amount)


def card_payment(date: str, wording: str, amount: float) -> CardTxn:
    return CardTxn(date, [wording], amount=amount)


# --------------------------------------------------------------------------


def main():
    dbs_dir = OUT_ROOT / "DBS"
    ocbc_dir = OUT_ROOT / "OCBC"

    # --- DBS deposit account, two months ---------------------------------
    generate_account_statement(
        dbs_dir / "Account Statements" / "SampleAccountStatement_Mar2024.pdf",
        DBS_ACCOUNT,
        statement_date="31 Mar 2024",
        period_start="01 Mar",
        sections=[
            AccountSection(
                name="DBS Multiplier Account",
                number="123-456789-0",
                opening_balance=4200.00,
                txns=[
                    dbs_salary("01 Mar", 3200.00),
                    dbs_card_purchase("03 Mar", "FAIRPRICE FINEST", 86.40),
                    dbs_paynow_out("05 Mar", "SAMPLE HOUSEMATE", 450.00),
                    dbs_giro("07 Mar", "SP SERVICES LTD", 128.90),
                    dbs_card_purchase("11 Mar", "KOPITIAM", 12.60),
                    dbs_paynow_in("14 Mar", "SAMPLE FRIEND", "1234567", 45.00),
                    dbs_card_purchase("18 Mar", "GUARDIAN HEALTH", 32.15),
                    dbs_giro("22 Mar", "SINGTEL MOBILE", 45.00),
                    dbs_paynow_out("26 Mar", "SAMPLE TUTOR", 160.00),
                    dbs_card_purchase("29 Mar", "SHENG SIONG", 54.25),
                ],
            )
        ],
    )

    # --- DBS consolidated statement: two accounts in one document --------
    # The consolidated eStatement is DBS's default, and it is the only
    # multi-account deposit statement any of these banks produce. Nothing else
    # in the fixture set exercises the engine's per-account sectioning on a
    # *deposit* statement (UOB's multi-account fixture is a card statement).
    generate_account_statement(
        dbs_dir / "Account Statements" / "SampleConsolidatedStatement_May2024.pdf",
        DBS_ACCOUNT,
        statement_date="31 May 2024",
        period_start="01 May",
        sections=[
            AccountSection(
                name="DBS Multiplier Account",
                number="123-456789-0",
                opening_balance=8000.00,
                txns=[
                    dbs_salary("01 May", 3200.00),
                    dbs_paynow_out("06 May", "SAMPLE HOUSEMATE", 450.00),
                    dbs_card_purchase("15 May", "FAIRPRICE FINEST", 91.20),
                ],
            ),
            AccountSection(
                name="POSB Savings Account",
                number="987-654321-0",
                opening_balance=1500.00,
                txns=[
                    dbs_card_purchase("08 May", "BUS/MRT TOP-UP", 30.00),
                    dbs_paynow_in("19 May", "SAMPLE PARENT", "2468013", 200.00),
                    dbs_card_purchase("27 May", "WATSONS", 18.40),
                ],
            ),
        ],
    )

    # --- DBS credit card -------------------------------------------------
    generate_card_statement(
        dbs_dir / "Card Statements" / "SampleCardStatement_Mar2024.pdf",
        DBS_CARD,
        statement_date="15 MAR 2024",
        cards=[
            CardSection(
                name="DBS SAMPLE CARD",
                number="0000-1111-2222-3333",
                previous_balance=312.45,
                txns=[
                    card_payment("18 FEB", "PAYMENT - DBS INTERNET/WIRELESS", 312.45),
                    charge("20 FEB", "GOLDEN VILLAGE CINEMAS", 32.00),
                    charge("23 FEB", "SPOTIFY SINGAPORE", 11.98),
                    charge("27 FEB", "GRAB SINGAPORE", 18.40),
                    charge("02 MAR", "UNIQLO SINGAPORE", 89.90),
                    charge("08 MAR", "COLD STORAGE", 76.35),
                ],
            )
        ],
    )
    # A card statement dated in January carrying December charges - the
    # year-wraparound case that a same-year fixture cannot cover.
    generate_card_statement(
        dbs_dir / "Card Statements" / "SampleCardStatement_Jan2025.pdf",
        DBS_CARD,
        statement_date="15 JAN 2025",
        cards=[
            CardSection(
                name="DBS SAMPLE CARD",
                number="0000-1111-2222-3333",
                previous_balance=228.63,
                txns=[
                    card_payment("18 DEC", "PAYMENT - DBS INTERNET/WIRELESS", 228.63),
                    charge("20 DEC", "TAKASHIMAYA", 156.00),
                    charge("26 DEC", "SHELL SERVICE STATION", 69.40),
                    charge("03 JAN", "FAIRPRICE XTRA", 112.80),
                ],
            )
        ],
    )

    # --- OCBC deposit account, two months --------------------------------
    generate_account_statement(
        ocbc_dir / "Account Statements" / "SampleAccountStatement_Mar2024.pdf",
        OCBC_ACCOUNT,
        statement_date="31 Mar 2024",
        period_start="01 Mar",
        sections=[
            AccountSection(
                name="OCBC 360 Account",
                number="501-234567-001",
                opening_balance=5200.00,
                txns=[
                    ocbc_salary("01 Mar", 3200.00),
                    ocbc_nets("03 Mar", "HAINANESE CHICKEN RICE", 6.70),
                    ocbc_paynow_out("05 Mar", "SAMPLE HOUSEMATE", 450.00),
                    ocbc_giro("07 Mar", "IRAS ITX", 99.36),
                    ocbc_nets("12 Mar", "SHENG SIONG SUPERMARKET", 48.20),
                    ocbc_paynow_in("16 Mar", "SAMPLE FRIEND", 62.00),
                    ocbc_giro("21 Mar", "SP SERVICES LTD", 121.44),
                    ocbc_nets("28 Mar", "TOAST BOX", 9.40),
                ],
            )
        ],
    )

    # --- OCBC credit card ------------------------------------------------
    # Dates are numeric and year-less here ("02/03"), unlike DBS's "05 MAR" -
    # the one place the two card layouts genuinely differ.
    generate_card_statement(
        ocbc_dir / "Card Statements" / "SampleCardStatement_Mar2024.pdf",
        OCBC_CARD,
        statement_date="15-03-2024",
        cards=[
            CardSection(
                name="OCBC SAMPLE CARD",
                number="0000-4444-5555-6666",
                previous_balance=204.18,
                txns=[
                    card_payment("18/02", "PAYMENT BY INTERNET", 204.18),
                    charge("20/02", "FOODIE EXPRESS SINGAPORE SG", 36.25),
                    charge("24/02", "URBAN TRANSIT CO. SINGAPORE SG", 1.38),
                    charge("01/03", "NTUC FAIRPRICE SINGAPORE SG", 82.60),
                    charge("07/03", "CIRCLES.LIFE SINGAPORE SG", 28.00),
                ],
            )
        ],
    )

    print("Generated DBS sample PDFs in", dbs_dir)
    print("Generated OCBC sample PDFs in", ocbc_dir)


if __name__ == "__main__":
    main()
