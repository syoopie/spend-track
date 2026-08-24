import re

from app.parsing.base import ParsedAccount, ParsedStatement, ParsedTransaction
from app.parsing.pdf_utils import Column, extract_words, group_into_lines, bucket_line

# Same rationale as account_statement.py: every page repeats a bilingual
# disclaimer + bank address footer whose words can fall inside our column
# x-ranges if not excluded before line-grouping.
FOOTER_TOP_CUTOFF = 780

COLUMNS = [
    Column("post_date", 50, 95, align="left"),
    Column("trans_date", 95, 145, align="left"),
    Column("description", 145, 470, align="left"),
    Column("amount", 470, 565, align="right"),
]

MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

CARD_NUMBER_RE = re.compile(r"(\d{4}-\d{4}-\d{4}-\d{4})")
STATEMENT_DATE_RE = re.compile(r"Statement Date\s+(\d{2}) (\w{3}) (\d{4})")
DATE_RE = re.compile(r"^(\d{2}) (\w{3})$")


def _statement_year_month(first_page_text: str) -> tuple[int, int]:
    m = STATEMENT_DATE_RE.search(first_page_text)
    if not m:
        raise ValueError("Could not find 'Statement Date' anchor")
    _day, mon_abbr, year = m.groups()
    return int(year), MONTHS[mon_abbr.upper()]


def _parse_amount(text: str) -> float:
    text = text.strip().upper()
    is_credit = text.endswith("CR")
    text = text[:-2].strip() if is_credit else text
    value = float(text.replace(",", ""))
    return value if is_credit else -value


def parse(pages) -> ParsedStatement:
    stmt_text = pages[0].extract_text() or ""
    statement_year, statement_month = _statement_year_month(stmt_text)

    tx_pages = [p for p in pages if "Description of Transaction" in (p.extract_text() or "")]
    if not tx_pages:
        raise ValueError("No card transaction table pages found")

    accounts_by_number: dict[str, ParsedAccount] = {}
    current_account: ParsedAccount | None = None
    current_tx: ParsedTransaction | None = None

    def finalize_tx():
        nonlocal current_tx
        if current_account is not None and current_tx is not None:
            current_account.transactions.append(current_tx)
        current_tx = None

    for page in tx_pages:
        words = [w for w in extract_words(page) if w.top < FOOTER_TOP_CUTOFF]
        lines = group_into_lines(words)
        rows = [bucket_line(line, COLUMNS) for line in lines]

        for idx, (line, row) in enumerate(zip(lines, rows)):
            post_text = row["post_date"].strip()
            trans_text = row["trans_date"].strip()
            desc_text = row["description"].strip()
            amount_text = row["amount"].strip()

            if post_text == "Post" and trans_text == "Trans":
                # Header row 1: the true per-card identity line is whichever
                # of the immediately preceding lines carries the card number -
                # found by walking backward, NOT by matching the card-number
                # pattern anywhere on the page (it also appears, differently
                # laid out, in the Summary table above the per-card sections).
                card_number = None
                for back in range(idx - 1, max(idx - 4, -1), -1):
                    m = CARD_NUMBER_RE.search(lines[back].text())
                    if m:
                        card_number = m.group(1)
                        card_name = lines[back - 1].text().strip() if back > 0 else "Credit Card"
                        break
                if card_number is None:
                    continue
                if card_number not in accounts_by_number:
                    accounts_by_number[card_number] = ParsedAccount(
                        bank_name="UOB",
                        account_number=card_number,
                        account_number_masked="••" + re.sub(r"\D", "", card_number)[-4:],
                        account_type=card_name,
                        is_card=True,
                    )
                finalize_tx()
                current_account = accounts_by_number[card_number]
                continue

            if not post_text and not trans_text and not desc_text:
                continue  # footer noise outside all column ranges

            if "(continued)" in line.text():
                # Repeated "<card number><holder> (continued)" identity line real
                # UOB card statements print at the top of continuation pages - see
                # the same guard/rationale in account_statement.py.
                continue

            if post_text == "Date" and trans_text == "Date":
                continue  # header row 2 ("Date Date SGD")
            if desc_text.startswith("PREVIOUS BALANCE"):
                continue
            if desc_text.startswith("SUB TOTAL") or desc_text.startswith("TOTAL BALANCE FOR"):
                finalize_tx()
                continue

            trans_match = DATE_RE.match(trans_text)
            if trans_match:
                finalize_tx()
                day, mon_abbr = trans_match.groups()
                month = MONTHS[mon_abbr.upper()]
                year = statement_year - 1 if month > statement_month else statement_year
                iso_date = f"{year:04d}-{month:02d}-{int(day):02d}"

                current_tx = ParsedTransaction(
                    transaction_date=iso_date,
                    raw_description=desc_text,
                    amount=_parse_amount(amount_text) if amount_text else 0.0,
                )
            elif current_tx is not None and desc_text:
                current_tx.raw_description += " " + desc_text

    finalize_tx()

    return ParsedStatement(bank_name="UOB", accounts=list(accounts_by_number.values()))
