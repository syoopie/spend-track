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
    balance: float = 0.0


def generate_account_statement(
    filename: str,
    period_label: str,
    period_start_date: str,  # "01 Feb" - used for the BALANCE B/F row
    account_type: str,
    account_number: str,
    opening_balance: float,
    txns: list[AccountTxn],
    closing_balance: float,
    total_withdrawals: float,
    total_deposits: float,
):
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
    return path


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
    sub_total: float


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


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Account statement 1: Feb 2024 (ordinary month, includes a
    # refund pair and the self-transfer-to-own-card exclusion scenario) ----
    txns = [
        AccountTxn("02 Feb", ["NETS Debit-Consumer", "SAMPLE MART 00000001", "xxxxxx0000"], withdrawal=12.40, balance=4987.60),
        AccountTxn("03 Feb", ["PAYNOW-FAST", "PIB0000000000000001", "SAMPLE PAYEE A", "OTHR Transfer - Mobile"], withdrawal=25.00, balance=4962.60),
        AccountTxn("04 Feb", ["Bill Payment", "mBK-UOB Cards", "0000111122223333"], withdrawal=150.00, balance=4812.60),
        AccountTxn("05 Feb", ["SAMPLE ONLINE STORE"], withdrawal=49.90, balance=4762.70),
        AccountTxn("07 Feb", ["Inward CR - GIRO", "SALA Salary Payment", "SAMPLE EMPLOYER PTE LTD", "SALARY"], deposit=3200.00, balance=7962.70),
        AccountTxn("09 Feb", ["PAYNOW-FAST", "PAYNOW OTHR", "SAMPLE PAYEE B", "SAMPLE PAYEE B"], withdrawal=18.50, balance=7944.20),
        AccountTxn("11 Feb", ["SAMPLE ONLINE STORE REFUND"], deposit=49.90, balance=7994.10),
        AccountTxn("14 Feb", ["NETS Debit-Consumer", "SAMPLE CAFE 00000002", "xxxxxx0000"], withdrawal=6.80, balance=7987.30),
        AccountTxn("18 Feb", ["Inward DR - GIRO", "TAXS S0000000A", "IRAS", "Income Tax"], withdrawal=120.00, balance=7867.30),
        AccountTxn("22 Feb", ["PAYNOW-FAST", "PIB0000000000000002", "SAMPLE PAYEE A", "OTHR Transfer - Mobile"], withdrawal=25.00, balance=7842.30),
        AccountTxn("29 Feb", ["Interest Credit"], deposit=1.15, balance=7843.45),
    ]
    generate_account_statement(
        "SampleAccountStatement_Feb2024.pdf",
        "01 Feb 2024 to 29 Feb 2024",
        "01 Feb",
        "One Account",
        "000-111-222-3",
        opening_balance=5000.00,
        txns=txns,
        closing_balance=7843.45,
        total_withdrawals=sum(t.withdrawal or 0 for t in txns),
        total_deposits=sum(t.deposit or 0 for t in txns),
    )

    # ---- Account statement 2: Mar 2024 (different month, same account -
    # exercises duplicate-detection across statements when both are loaded) ----
    txns2 = [
        AccountTxn("01 Mar", ["NETS Debit-Consumer", "SAMPLE MART 00000003", "xxxxxx0000"], withdrawal=15.20, balance=7828.25),
        AccountTxn("05 Mar", ["PAYNOW-FAST", "PIB0000000000000003", "SAMPLE PAYEE C", "OTHR Transfer - UEN"], withdrawal=88.00, balance=7740.25),
        AccountTxn("08 Mar", ["Bill Payment", "mBK-UOB Cards", "0000111122223333"], withdrawal=95.40, balance=7644.85),
        AccountTxn("12 Mar", ["Inward CR - GIRO", "SALA Salary Payment", "SAMPLE EMPLOYER PTE LTD", "SALARY"], deposit=3200.00, balance=10844.85),
        AccountTxn("20 Mar", ["PAYNOW-FAST", "PAYNOW OTHR", "SAMPLE PAYEE B", "SAMPLE PAYEE B"], withdrawal=18.50, balance=10826.35),
        AccountTxn("31 Mar", ["Interest Credit"], deposit=1.42, balance=10827.77),
    ]
    generate_account_statement(
        "SampleAccountStatement_Mar2024.pdf",
        "01 Mar 2024 to 31 Mar 2024",
        "01 Mar",
        "One Account",
        "000-111-222-3",
        opening_balance=7843.45,
        txns=txns2,
        closing_balance=10827.77,
        total_withdrawals=sum(t.withdrawal or 0 for t in txns2),
        total_deposits=sum(t.deposit or 0 for t in txns2),
    )

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
        sub_total=95.40 - 150.00 + sum(-t.amount for t in card1_txns if t.amount < 0),
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
        sub_total=sum(-t.amount for t in cardA_txns),
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
        sub_total=200.00 - 200.00 + sum(-t.amount for t in cardB_txns if t.amount < 0),
    )
    generate_card_statement(
        "SampleCardStatement_MultiCard_Mar2024.pdf", "20 MAR 2024", "12 APR 2024", [cardA, cardB]
    )

    print("Generated sample PDFs in", OUT_DIR)


if __name__ == "__main__":
    main()
