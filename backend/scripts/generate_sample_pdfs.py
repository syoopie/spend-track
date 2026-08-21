"""Generate synthetic UOB-format sample statements for the public repo.

The real statements in `PDF Examples/` contain a real name, home address,
and account/card numbers, so they're gitignored. These generated PDFs use
the exact column x-positions reverse-engineered in
`app/parsing/uob/{account_statement,card_statement}.py` (see COLUMNS in
each) so they are structurally faithful to the real layout and - as a
bonus - parse cleanly with the real parser, which doubles as a fidelity
check. Every value (name, address, account/card numbers, reference
numbers, transfer counterparties) is an obvious placeholder.

Run with: uv run python scripts/generate_sample_pdfs.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = A4  # 595.295 x 841.895, matches the real statements
FOOTER_TOP_CUTOFF = 780  # must match parsing/*.py - text below this is ignored by the parser
FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

OUT_DIR = Path(__file__).resolve().parents[2] / "PDF Examples (Sanitized)" / "UOB"

SAMPLE_NAME = "SAMPLE CUSTOMER"
SAMPLE_ADDRESS = ["1 SAMPLE STREET", "#01-01 EXAMPLE BUILDING", "SINGAPORE 000000"]
SYNTHETIC_NOTICE = "SAMPLE DATA - SYNTHETIC, NOT AN OFFICIAL UOB DOCUMENT - all names, addresses and numbers below are fictional placeholders."


def y_for_top(top: float, font_size: float = 9) -> float:
    """Convert a pdfplumber-style `top` (distance from page top) to a
    reportlab baseline y (distance from page bottom, ascending)."""
    return PAGE_H - top - font_size * 0.8


class Doc:
    def __init__(self, path: Path):
        self.c = canvas.Canvas(str(path), pagesize=A4)
        self.page_num = 1

    def text(self, x: float, top: float, s: str, size: float = 9, font: str = FONT):
        self.c.setFont(font, size)
        self.c.drawString(x, y_for_top(top, size), s)

    def text_right(self, x_right: float, top: float, s: str, size: float = 9, font: str = FONT):
        self.c.setFont(font, size)
        self.c.drawRightString(x_right, y_for_top(top, size), s)

    def footer(self):
        self.text(36, 800, SYNTHETIC_NOTICE, size=7)
        self.text(36, 815, f"Page {self.page_num}", size=7)
        self.text(36, 828, "United Overseas Bank Limited (sample letterhead - synthetic document)", size=7)

    def new_page(self):
        self.footer()
        self.c.showPage()
        self.page_num += 1

    def save(self):
        self.footer()
        self.c.save()


# --------------------------------------------------------------------------
# Account Statement
# --------------------------------------------------------------------------

# Matches Column definitions in app/parsing/uob/account_statement.py
ACC_DATE_X = 52.5
ACC_DESC_X = 120.5
ACC_WITHDRAWALS_RIGHT = 386.0
ACC_DEPOSITS_RIGHT = 465.5
ACC_BALANCE_RIGHT = 545.0


@dataclass
class AccountTxn:
    date: str  # "05 Feb"
    lines: list[str]  # first line + continuation lines
    withdrawal: float | None = None
    deposit: float | None = None
    balance: float = 0.0  # filled in by _apply_running_balance


def _apply_running_balance(opening_balance: float, txns: list[AccountTxn]) -> float:
    """Computes each txn's running balance (and returns the closing balance)
    from opening_balance + each txn's effect, instead of requiring every
    balance/total to be hand-computed and kept in sync by whoever edits the
    transaction list."""
    running = opening_balance
    for txn in txns:
        if txn.withdrawal is not None:
            running -= txn.withdrawal
        if txn.deposit is not None:
            running += txn.deposit
        txn.balance = round(running, 2)
    return round(running, 2)


def generate_account_statement(
    filename: str,
    period_label: str,
    period_start_date: str,  # "01 Feb" - used for the BALANCE B/F row
    account_type: str,
    account_number: str,
    opening_balance: float,
    txns: list[AccountTxn],
):
    closing_balance = _apply_running_balance(opening_balance, txns)
    total_withdrawals = round(sum(t.withdrawal or 0 for t in txns), 2)
    total_deposits = round(sum(t.deposit or 0 for t in txns), 2)
    path = OUT_DIR / "Account Statements" / filename
    doc = Doc(path)

    # --- page 1: summary (content here isn't parsed - only used for detect() / period regex)
    doc.text(36, 40, "Contact Us", size=10, font=FONT_BOLD)
    doc.text(36, 60, SAMPLE_NAME, size=10, font=FONT_BOLD)
    for i, line in enumerate(SAMPLE_ADDRESS):
        doc.text(36, 72 + i * 12, line)
    doc.text(36, 140, "Statement of Account", size=14, font=FONT_BOLD)
    doc.text(36, 158, f"Period: {period_label}")
    doc.text(36, 180, "Account Overview", size=11, font=FONT_BOLD)
    doc.text(36, 198, f"Deposits {closing_balance:,.2f}")
    doc.new_page()

    # --- transaction table page(s)
    def draw_header(continued: bool):
        doc.text(52.5, 112, "Account Transaction Details", size=11, font=FONT_BOLD)
        suffix = " (continued)" if continued else ""
        doc.text(52.5, 132, f"{account_type} {account_number}{suffix}", font=FONT_BOLD)
        doc.text(ACC_DATE_X, 155.9, "Date", font=FONT_BOLD)
        doc.text(ACC_DESC_X, 155.9, "Description", font=FONT_BOLD)
        doc.text_right(ACC_WITHDRAWALS_RIGHT, 155.0, "Withdrawals", font=FONT_BOLD)
        doc.text_right(ACC_DEPOSITS_RIGHT, 155.0, "Deposits", font=FONT_BOLD)
        doc.text_right(ACC_BALANCE_RIGHT, 155.0, "Balance", font=FONT_BOLD)
        doc.text_right(ACC_WITHDRAWALS_RIGHT, 163.3, "SGD", size=7)
        doc.text_right(ACC_DEPOSITS_RIGHT, 163.3, "SGD", size=7)
        doc.text_right(ACC_BALANCE_RIGHT, 163.3, "SGD", size=7)

    draw_header(continued=False)
    top = 178.0
    LINE_H = 12.5

    doc.text(ACC_DATE_X, top, period_start_date)
    doc.text(ACC_DESC_X, top, "BALANCE B/F")
    doc.text_right(ACC_BALANCE_RIGHT, top, f"{opening_balance:,.2f}")
    top += LINE_H

    for txn in txns:
        if top > FOOTER_TOP_CUTOFF - 20:
            doc.new_page()
            draw_header(continued=True)
            top = 178.0
        doc.text(ACC_DATE_X, top, txn.date)
        doc.text(ACC_DESC_X, top, txn.lines[0])
        if txn.withdrawal is not None:
            doc.text_right(ACC_WITHDRAWALS_RIGHT, top, f"{txn.withdrawal:,.2f}")
        if txn.deposit is not None:
            doc.text_right(ACC_DEPOSITS_RIGHT, top, f"{txn.deposit:,.2f}")
        doc.text_right(ACC_BALANCE_RIGHT, top, f"{txn.balance:,.2f}")
        top += LINE_H
        for extra in txn.lines[1:]:
            if top > FOOTER_TOP_CUTOFF - 20:
                doc.new_page()
                draw_header(continued=True)
                top = 178.0
            doc.text(ACC_DESC_X, top, extra)
            top += LINE_H

    if top > FOOTER_TOP_CUTOFF - 20:
        doc.new_page()
        draw_header(continued=True)
        top = 178.0
    doc.text(ACC_DESC_X, top, "Total")
    doc.text_right(ACC_WITHDRAWALS_RIGHT, top, f"{total_withdrawals:,.2f}")
    doc.text_right(ACC_DEPOSITS_RIGHT, top, f"{total_deposits:,.2f}")
    doc.text_right(ACC_BALANCE_RIGHT, top, f"{closing_balance:,.2f}")

    doc.save()
    return path, closing_balance


# --------------------------------------------------------------------------
# Card Statement
# --------------------------------------------------------------------------

# Matches Column definitions in app/parsing/uob/card_statement.py
CARD_POST_X = 55.0
CARD_TRANS_X = 100.0
CARD_DESC_X = 148.8
CARD_AMOUNT_RIGHT = 545.0


@dataclass
class CardTxn:
    post_date: str
    trans_date: str
    lines: list[str]
    amount: float  # negative = charge, positive = credit (rendered with CR suffix)


@dataclass
class Card:
    name: str
    number: str  # "0000-1111-2222-3333"
    holder: str
    previous_balance: float
    txns: list[CardTxn]
    sub_total: float = field(init=False)  # PREVIOUS BALANCE + charges - credits, computed below

    def __post_init__(self):
        # amount: negative = charge (adds to what's owed), positive = credit
        # (reduces it) - see CLAUDE.md's note that SUB TOTAL is a running
        # balance, not just this statement's net charges.
        self.sub_total = round(self.previous_balance - sum(t.amount for t in self.txns), 2)


def generate_card_statement(filename: str, statement_date: str, due_date: str, cards: list[Card]):
    path = OUT_DIR / "Card Statements" / filename
    doc = Doc(path)

    # --- page 1 top: summary
    doc.text(36, 40, "Statement Summary", size=11, font=FONT_BOLD)
    doc.text(36, 58, f"Statement Date {statement_date}")
    doc.text(36, 96, SAMPLE_NAME, size=10, font=FONT_BOLD)
    for i, line in enumerate(SAMPLE_ADDRESS):
        doc.text(36, 108 + i * 12, line)
    doc.text(36, 160, "Credit Card(s) Statement", size=13, font=FONT_BOLD)

    doc.text(36, 190, "Summary", size=10, font=FONT_BOLD)
    doc.text(36, 208, "Card Name")
    doc.text(200, 208, "Card Number")
    doc.text(340, 208, "Name on Card")
    doc.text_right(520, 208, "Amount to Pay SGD")
    summary_top = 226
    for card in cards:
        doc.text(36, summary_top, card.name)
        doc.text(200, summary_top, card.number)
        doc.text(340, summary_top, card.holder)
        doc.text_right(520, summary_top, f"{card.sub_total:,.2f}")
        summary_top += 14

    top = summary_top + 30

    def draw_card_header(card: Card, continued: bool):
        nonlocal top
        if top > FOOTER_TOP_CUTOFF - 40:
            doc.new_page()
            top = 60.0
        doc.text(36, top, card.name, size=11, font=FONT_BOLD)
        top += 18
        suffix = " (continued)" if continued else ""
        doc.text(36, top, f"{card.number}{card.holder}{suffix}", font=FONT_BOLD)
        top += 20
        doc.text(CARD_POST_X, top, "Post", font=FONT_BOLD)
        doc.text(CARD_TRANS_X, top, "Trans", font=FONT_BOLD)
        doc.text(CARD_DESC_X, top, "Description of Transaction", font=FONT_BOLD)
        doc.text_right(CARD_AMOUNT_RIGHT, top, "Transaction Amount", font=FONT_BOLD)
        top += 8.4
        doc.text(CARD_POST_X, top, "Date", size=7)
        doc.text(CARD_TRANS_X, top, "Date", size=7)
        doc.text_right(CARD_AMOUNT_RIGHT, top, "SGD", size=7)
        top += 20

    LINE_H = 12.5
    for card in cards:
        draw_card_header(card, continued=False)
        doc.text(CARD_DESC_X, top, "PREVIOUS BALANCE")
        doc.text_right(CARD_AMOUNT_RIGHT, top, f"{card.previous_balance:,.2f}")
        top += LINE_H

        for txn in card.txns:
            if top > FOOTER_TOP_CUTOFF - 20:
                doc.new_page()
                top = 60.0
                draw_card_header(card, continued=True)
            doc.text(CARD_POST_X, top, txn.post_date)
            doc.text(CARD_TRANS_X, top, txn.trans_date)
            doc.text(CARD_DESC_X, top, txn.lines[0])
            amount_text = f"{txn.amount:,.2f}CR" if txn.amount > 0 else f"{-txn.amount:,.2f}"
            doc.text_right(CARD_AMOUNT_RIGHT, top, amount_text)
            top += LINE_H
            for extra in txn.lines[1:]:
                if top > FOOTER_TOP_CUTOFF - 20:
                    doc.new_page()
                    top = 60.0
                    draw_card_header(card, continued=True)
                doc.text(CARD_DESC_X, top, extra)
                top += LINE_H

        if top > FOOTER_TOP_CUTOFF - 20:
            doc.new_page()
            top = 60.0
        doc.text(CARD_DESC_X, top, "SUB TOTAL")
        doc.text_right(CARD_AMOUNT_RIGHT, top, f"{card.sub_total:,.2f}")
        top += LINE_H
        doc.text(CARD_DESC_X, top, f"TOTAL BALANCE FOR {card.name}")
        doc.text_right(CARD_AMOUNT_RIGHT, top, f"{card.sub_total:,.2f}")
        top += 30

    doc.save()
    return path


def ref(n: int) -> str:
    """A fake reference number in the same digit-length shape as real ones."""
    return f"Ref No. : {n:024d}"


def _opening_balance_for_closing(txns: list[AccountTxn], target_closing: float) -> float:
    """Solves for the opening balance that makes this txn list close at
    target_closing, so a new statement can be chained to land exactly on an
    existing, already-committed statement's fixed opening balance without
    hand-computing the running total."""
    net = sum(t.deposit or 0 for t in txns) - sum(t.withdrawal or 0 for t in txns)
    return round(target_closing - net, 2)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Account statement 0: Jan 2024 (chained to close exactly at Feb's
    # fixed opening_balance below, so the two-month history is continuous) ----
    txns0 = [
        AccountTxn("02 Jan", ["NETS Debit-Consumer", "NTUC FAIRPRICE 00000010", "xxxxxx0000"], withdrawal=32.50),
        AccountTxn("04 Jan", ["Bill Payment", "mBK-UOB Cards", "0000111122223333"], withdrawal=110.00),
        AccountTxn("06 Jan", ["PAYNOW-FAST", "PIB0000000000000010", "SAMPLE PAYEE A", "OTHR Transfer - Mobile"], withdrawal=20.00),
        AccountTxn("08 Jan", ["NETS Debit-Consumer", "STARBUCKS 00000011", "xxxxxx0000"], withdrawal=7.80),
        AccountTxn("10 Jan", ["GRAB* RIDE SINGAPORE"], withdrawal=14.20),
        AccountTxn("12 Jan", ["NETFLIX.COM"], withdrawal=15.98),
        AccountTxn("15 Jan", ["Inward CR - GIRO", "SALA Salary Payment", "SAMPLE EMPLOYER PTE LTD", "SALARY"], deposit=3200.00),
        AccountTxn("18 Jan", ["SHOPEE *ORDER 00000012"], withdrawal=38.60),
        AccountTxn("20 Jan", ["PAYNOW-FAST", "PAYNOW OTHR", "SAMPLE PAYEE B", "SAMPLE PAYEE B"], withdrawal=18.50),
        AccountTxn("24 Jan", ["DECATHLON SINGAPORE"], withdrawal=45.00),
        AccountTxn("27 Jan", ["Inward DR - GIRO", "TAXS S0000000B", "IRAS", "Income Tax"], withdrawal=95.00),
        AccountTxn("29 Jan", ["Interest Credit"], deposit=1.08),
    ]
    generate_account_statement(
        "SampleAccountStatement_Jan2024.pdf",
        "01 Jan 2024 to 31 Jan 2024",
        "01 Jan",
        "One Account",
        "000-111-222-3",
        opening_balance=_opening_balance_for_closing(txns0, target_closing=5000.00),
        txns=txns0,
    )

    # ---- Account statement 1: Feb 2024 (ordinary month, includes a
    # refund pair and the self-transfer-to-own-card exclusion scenario) ----
    txns = [
        AccountTxn("02 Feb", ["NETS Debit-Consumer", "SAMPLE MART 00000001", "xxxxxx0000"], withdrawal=12.40),
        AccountTxn("03 Feb", ["PAYNOW-FAST", "PIB0000000000000001", "SAMPLE PAYEE A", "OTHR Transfer - Mobile"], withdrawal=25.00),
        AccountTxn("04 Feb", ["Bill Payment", "mBK-UOB Cards", "0000111122223333"], withdrawal=150.00),
        AccountTxn("05 Feb", ["SAMPLE ONLINE STORE"], withdrawal=49.90),
        AccountTxn("07 Feb", ["Inward CR - GIRO", "SALA Salary Payment", "SAMPLE EMPLOYER PTE LTD", "SALARY"], deposit=3200.00),
        AccountTxn("09 Feb", ["PAYNOW-FAST", "PAYNOW OTHR", "SAMPLE PAYEE B", "SAMPLE PAYEE B"], withdrawal=18.50),
        AccountTxn("11 Feb", ["SAMPLE ONLINE STORE REFUND"], deposit=49.90),
        AccountTxn("14 Feb", ["NETS Debit-Consumer", "SAMPLE CAFE 00000002", "xxxxxx0000"], withdrawal=6.80),
        AccountTxn("18 Feb", ["Inward DR - GIRO", "TAXS S0000000A", "IRAS", "Income Tax"], withdrawal=120.00),
        AccountTxn("22 Feb", ["PAYNOW-FAST", "PIB0000000000000002", "SAMPLE PAYEE A", "OTHR Transfer - Mobile"], withdrawal=25.00),
        AccountTxn("29 Feb", ["Interest Credit"], deposit=1.15),
    ]
    generate_account_statement(
        "SampleAccountStatement_Feb2024.pdf",
        "01 Feb 2024 to 29 Feb 2024",
        "01 Feb",
        "One Account",
        "000-111-222-3",
        opening_balance=5000.00,
        txns=txns,
    )

    # ---- Account statement 2: Mar 2024 (different month, same account -
    # exercises duplicate-detection across statements when both are loaded) ----
    txns2 = [
        AccountTxn("01 Mar", ["NETS Debit-Consumer", "SAMPLE MART 00000003", "xxxxxx0000"], withdrawal=15.20),
        AccountTxn("05 Mar", ["PAYNOW-FAST", "PIB0000000000000003", "SAMPLE PAYEE C", "OTHR Transfer - UEN"], withdrawal=88.00),
        AccountTxn("08 Mar", ["Bill Payment", "mBK-UOB Cards", "0000111122223333"], withdrawal=95.40),
        AccountTxn("12 Mar", ["Inward CR - GIRO", "SALA Salary Payment", "SAMPLE EMPLOYER PTE LTD", "SALARY"], deposit=3200.00),
        AccountTxn("20 Mar", ["PAYNOW-FAST", "PAYNOW OTHR", "SAMPLE PAYEE B", "SAMPLE PAYEE B"], withdrawal=18.50),
        AccountTxn("31 Mar", ["Interest Credit"], deposit=1.42),
    ]
    _, mar_closing = generate_account_statement(
        "SampleAccountStatement_Mar2024.pdf",
        "01 Mar 2024 to 31 Mar 2024",
        "01 Mar",
        "One Account",
        "000-111-222-3",
        opening_balance=7843.45,
        txns=txns2,
    )

    # ---- Account statement 3: Apr 2024 (insurance GIRO deduction + an
    # Interactive Brokers PayNow transfer, chained from Mar's closing) ----
    txns3 = [
        AccountTxn("02 Apr", ["NETS Debit-Consumer", "COLD STORAGE 00000013", "xxxxxx0000"], withdrawal=58.40),
        AccountTxn("04 Apr", ["Bill Payment", "mBK-UOB Cards", "0000111122223333"], withdrawal=180.00),
        AccountTxn("06 Apr", ["Inward Dr Giro Othr", "E18127522491", "Income Insurance Lim", "1812752249"], withdrawal=210.50),
        AccountTxn("09 Apr", ["SAMPLE ONLINE STORE"], withdrawal=59.90),
        AccountTxn("11 Apr", ["PAYNOW-FAST", "PIB0000000000000020", "INTERACTIVE BR SG- R", "OTHR Transfer - Mobile"], withdrawal=500.00),
        AccountTxn("13 Apr", ["IKEA SINGAPORE"], withdrawal=89.90),
        AccountTxn("15 Apr", ["Inward CR - GIRO", "SALA Salary Payment", "SAMPLE EMPLOYER PTE LTD", "SALARY"], deposit=3200.00),
        AccountTxn("17 Apr", ["WATSONS SINGAPORE"], withdrawal=22.30),
        AccountTxn("20 Apr", ["KINOKUNIYA SINGAPORE"], withdrawal=48.00),
        AccountTxn("24 Apr", ["PAYNOW-FAST", "PAYNOW OTHR", "SAMPLE PAYEE B", "SAMPLE PAYEE B"], withdrawal=18.50),
        AccountTxn("26 Apr", ["SAMPLE ONLINE STORE REFUND"], deposit=59.90),
        AccountTxn("30 Apr", ["Interest Credit"], deposit=1.62),
    ]
    _, apr_closing = generate_account_statement(
        "SampleAccountStatement_Apr2024.pdf",
        "01 Apr 2024 to 30 Apr 2024",
        "01 Apr",
        "One Account",
        "000-111-222-3",
        opening_balance=mar_closing,
        txns=txns3,
    )

    # ---- Account statement 4: May 2024 (property tax + more merchant
    # variety, chained from Apr's closing) ----
    txns4 = [
        AccountTxn("03 May", ["NETS Debit-Consumer", "SHENG SIONG 00000014", "xxxxxx0000"], withdrawal=41.20),
        AccountTxn("05 May", ["SP GROUP"], withdrawal=145.60),
        AccountTxn("07 May", ["Bill Payment", "mBK-UOB Cards", "0000111122223333"], withdrawal=150.00),
        AccountTxn("09 May", ["GRABCAR SINGAPORE"], withdrawal=16.80),
        AccountTxn("11 May", ["MCDONALDS SINGAPORE"], withdrawal=9.40),
        AccountTxn("13 May", ["PAYNOW-FAST", "PIB0000000000000030", "SAMPLE PAYEE C", "OTHR Transfer - UEN"], withdrawal=65.00),
        AccountTxn("15 May", ["Inward CR - GIRO", "SALA Salary Payment", "SAMPLE EMPLOYER PTE LTD", "SALARY"], deposit=3200.00),
        AccountTxn("18 May", ["RAFFLES MEDICAL CLINIC"], withdrawal=88.00),
        AccountTxn("20 May", ["COURSERA SINGAPORE"], withdrawal=52.00),
        AccountTxn("22 May", ["Inward DR - GIRO", "TAXS S0000000C", "IRAS", "Property Tax"], withdrawal=310.00),
        AccountTxn("25 May", ["PAYNOW-FAST", "PAYNOW OTHR", "SAMPLE PAYEE B", "SAMPLE PAYEE B"], withdrawal=18.50),
        AccountTxn("28 May", ["NETS Debit-Consumer", "SAMPLE CAFE 00000015", "xxxxxx0000"], withdrawal=6.50),
        AccountTxn("31 May", ["Interest Credit"], deposit=1.89),
    ]
    _, may_closing = generate_account_statement(
        "SampleAccountStatement_May2024.pdf",
        "01 May 2024 to 31 May 2024",
        "01 May",
        "One Account",
        "000-111-222-3",
        opening_balance=apr_closing,
        txns=txns4,
    )

    # ---- Account statement 5: Jun 2024 (a second insurance + investing
    # month, chained from May's closing) ----
    txns5 = [
        AccountTxn("02 Jun", ["NETS Debit-Consumer", "NTUC FAIRPRICE 00000016", "xxxxxx0000"], withdrawal=37.90),
        AccountTxn("04 Jun", ["Bill Payment", "mBK-UOB Cards", "0000111122223333"], withdrawal=165.00),
        AccountTxn("06 Jun", ["ANYTIME FITNESS SINGAPORE"], withdrawal=120.00),
        AccountTxn("08 Jun", ["GOLDEN VILLAGE VIVOCITY"], withdrawal=32.00),
        AccountTxn("10 Jun", ["Inward Dr Giro Othr", "E18127522500", "Income Insurance Lim", "1812752260"], withdrawal=210.50),
        AccountTxn("12 Jun", ["PAYNOW-FAST", "PIB0000000000000040", "INTERACTIVE BR SG- R", "OTHR Transfer - Mobile"], withdrawal=400.00),
        AccountTxn("15 Jun", ["Inward CR - GIRO", "SALA Salary Payment", "SAMPLE EMPLOYER PTE LTD", "SALARY"], deposit=3200.00),
        AccountTxn("18 Jun", ["LAZADA SINGAPORE"], withdrawal=64.30),
        AccountTxn("20 Jun", ["NAIL SPA SINGAPORE"], withdrawal=58.00),
        AccountTxn("23 Jun", ["PAYNOW-FAST", "PAYNOW OTHR", "SAMPLE PAYEE B", "SAMPLE PAYEE B"], withdrawal=18.50),
        AccountTxn("26 Jun", ["HOME-FIX SINGAPORE"], withdrawal=45.60),
        AccountTxn("30 Jun", ["Interest Credit"], deposit=2.10),
    ]
    generate_account_statement(
        "SampleAccountStatement_Jun2024.pdf",
        "01 Jun 2024 to 30 Jun 2024",
        "01 Jun",
        "One Account",
        "000-111-222-3",
        opening_balance=may_closing,
        txns=txns5,
    )

    # ---- Card statement 0: single card, Jan 2024 (first statement of the
    # card's history in this dataset - no PAYMT credit yet) ----
    card0_txns = [
        CardTxn("04 JAN", "04 JAN", ["PAYMT THRU E-BANK/HOMEB/CYBERB (SAMPLE)"], amount=110.00),
        CardTxn("06 JAN", "05 JAN", ["BUS/MRT 000000010 SINGAPORE", ref(11)], amount=-3.20),
        CardTxn("09 JAN", "08 JAN", ["NTUC FAIRPRICE SINGAPORE", ref(12)], amount=-28.50),
        CardTxn("14 JAN", "13 JAN", ["SPOTIFY SINGAPORE", ref(13)], amount=-11.98),
        CardTxn("18 JAN", "17 JAN", ["KOI THE SINGAPORE", ref(14)], amount=-6.20),
        CardTxn("22 JAN", "21 JAN", ["LAZADA SINGAPORE", ref(15)], amount=-41.52),
    ]
    card0 = Card(
        name="UOB SAMPLE CARD",
        number="0000-1111-2222-3333",
        holder="SAMPLE CUSTOMER",
        previous_balance=110.00,
        txns=card0_txns,
    )
    generate_card_statement("SampleCardStatement_Jan2024.pdf", "20 JAN 2024", "12 FEB 2024", [card0])

    # ---- Card statement 1: single card, Feb 2024 (mirrors the account
    # statement's mBK-UOB Cards bill payment as the matching CR side) ----
    card1_txns = [
        CardTxn("04 FEB", "04 FEB", ["PAYMT THRU E-BANK/HOMEB/CYBERB (SAMPLE)"], amount=150.00),
        CardTxn("06 FEB", "05 FEB", ["BUS/MRT 000000001 SINGAPORE", ref(1)], amount=-2.50),
        CardTxn("08 FEB", "07 FEB", ["SAMPLE CAFE 00000004 SINGAPORE", ref(2)], amount=-6.20),
        CardTxn("10 FEB", "09 FEB", ["SAMPLE STREAMING SERVICE", ref(3)], amount=-15.98),
        CardTxn("14 FEB", "13 FEB", ["SAMPLE SUPERMARKET SINGAPORE", ref(4)], amount=-42.30),
        CardTxn("18 FEB", "17 FEB", ["SAMPLE ONLINE MARKETPLACE", ref(5)], amount=-27.90),
    ]
    card1 = Card(
        name="UOB SAMPLE CARD",
        number="0000-1111-2222-3333",
        holder="SAMPLE CUSTOMER",
        previous_balance=95.40,
        txns=card1_txns,
    )
    generate_card_statement("SampleCardStatement_Feb2024.pdf", "20 FEB 2024", "12 MAR 2024", [card1])

    # ---- Card statement 2: TWO cards in one statement, Mar 2024 -
    # demonstrates the multi-card parsing path (no real sample had this) ----
    cardA_txns = [
        CardTxn("03 MAR", "02 MAR", ["BUS/MRT 000000002 SINGAPORE", ref(6)], amount=-3.20),
        CardTxn("09 MAR", "08 MAR", ["SAMPLE RESTAURANT SINGAPORE", ref(7)], amount=-34.50),
        CardTxn("15 MAR", "14 MAR", ["SAMPLE STREAMING SERVICE", ref(8)], amount=-15.98),
    ]
    cardA = Card(
        name="UOB SAMPLE CARD",
        number="0000-1111-2222-3333",
        holder="SAMPLE CUSTOMER",
        previous_balance=0.00,
        txns=cardA_txns,
    )
    cardB_txns = [
        CardTxn("05 MAR", "04 MAR", ["SAMPLE AIRLINE BOOKING", ref(9)], amount=-410.00),
        CardTxn("12 MAR", "11 MAR", ["PAYMT THRU E-BANK/HOMEB/CYBERB (SAMPLE)"], amount=200.00),
        CardTxn("20 MAR", "19 MAR", ["SAMPLE ELECTRONICS STORE", ref(10)], amount=-89.00),
    ]
    cardB = Card(
        name="UOB SAMPLE TRAVEL CARD",
        number="0000-4444-5555-6666",
        holder="SAMPLE CUSTOMER",
        previous_balance=200.00,
        txns=cardB_txns,
    )
    generate_card_statement(
        "SampleCardStatement_MultiCard_Mar2024.pdf", "20 MAR 2024", "12 APR 2024", [cardA, cardB]
    )

    # ---- Card statement 3: single card, Apr 2024 ----
    card3_txns = [
        CardTxn("04 APR", "04 APR", ["PAYMT THRU E-BANK/HOMEB/CYBERB (SAMPLE)"], amount=180.00),
        CardTxn("06 APR", "05 APR", ["GRABCAR SINGAPORE", ref(16)], amount=-13.50),
        CardTxn("10 APR", "09 APR", ["MCDONALDS SINGAPORE", ref(17)], amount=-8.90),
        CardTxn("14 APR", "13 APR", ["SEPHORA SINGAPORE", ref(18)], amount=-64.00),
        CardTxn("18 APR", "17 APR", ["DECATHLON SINGAPORE", ref(19)], amount=-55.00),
        CardTxn("22 APR", "21 APR", ["GYMBOXX SINGAPORE", ref(20)], amount=-88.00),
    ]
    card3 = Card(
        name="UOB SAMPLE CARD",
        number="0000-1111-2222-3333",
        holder="SAMPLE CUSTOMER",
        previous_balance=90.00,
        txns=card3_txns,
    )
    generate_card_statement("SampleCardStatement_Apr2024.pdf", "20 APR 2024", "12 MAY 2024", [card3])

    # ---- Card statement 4: single card, May 2024 ----
    card4_txns = [
        CardTxn("07 MAY", "07 MAY", ["PAYMT THRU E-BANK/HOMEB/CYBERB (SAMPLE)"], amount=150.00),
        CardTxn("09 MAY", "08 MAY", ["COMFORTDELGRO SINGAPORE", ref(21)], amount=-18.40),
        CardTxn("12 MAY", "11 MAY", ["KFC SINGAPORE", ref(22)], amount=-11.50),
        CardTxn("16 MAY", "15 MAY", ["WATSONS SINGAPORE", ref(23)], amount=-19.90),
        CardTxn("20 MAY", "19 MAY", ["UNITY PHARMACY SINGAPORE", ref(24)], amount=-24.60),
        CardTxn("24 MAY", "23 MAY", ["SPOTIFY SINGAPORE", ref(25)], amount=-11.98),
    ]
    card4 = Card(
        name="UOB SAMPLE CARD",
        number="0000-1111-2222-3333",
        holder="SAMPLE CUSTOMER",
        previous_balance=70.00,
        txns=card4_txns,
    )
    generate_card_statement("SampleCardStatement_May2024.pdf", "20 MAY 2024", "12 JUN 2024", [card4])

    # ---- Card statement 5: single card, Jun 2024 ----
    card5_txns = [
        CardTxn("04 JUN", "04 JUN", ["PAYMT THRU E-BANK/HOMEB/CYBERB (SAMPLE)"], amount=165.00),
        CardTxn("06 JUN", "05 JUN", ["GYMBOXX SINGAPORE", ref(26)], amount=-45.00),
        CardTxn("10 JUN", "09 JUN", ["GOLDEN VILLAGE VIVOCITY", ref(27)], amount=-16.00),
        CardTxn("14 JUN", "13 JUN", ["TOAST BOX SINGAPORE", ref(28)], amount=-5.60),
        CardTxn("18 JUN", "17 JUN", ["SHOPEE *ORDER SINGAPORE", ref(29)], amount=-33.20),
        CardTxn("22 JUN", "21 JUN", ["HOME-FIX SINGAPORE", ref(30)], amount=-22.00),
    ]
    card5 = Card(
        name="UOB SAMPLE CARD",
        number="0000-1111-2222-3333",
        holder="SAMPLE CUSTOMER",
        previous_balance=50.00,
        txns=card5_txns,
    )
    generate_card_statement("SampleCardStatement_Jun2024.pdf", "20 JUN 2024", "12 JUL 2024", [card5])

    print("Generated sample PDFs in", OUT_DIR)


if __name__ == "__main__":
    main()
