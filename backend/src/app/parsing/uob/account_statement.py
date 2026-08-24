import re

from app.parsing.base import ParsedAccount, ParsedStatement, ParsedTransaction
from app.parsing.pdf_utils import Column, extract_words, group_into_lines, bucket_line

# Every page repeats a bilingual disclaimer + bank address footer starting
# around this y-coordinate; words from it can fall inside our column x-ranges
# (e.g. "UOB Plaza Singapore" lands inside the description column) and must
# be excluded before line-grouping, not filtered after the fact.
FOOTER_TOP_CUTOFF = 780

COLUMNS = [
    Column("date", 45, 100, align="left"),
    Column("description", 100, 330, align="left"),
    Column("withdrawals", 330, 400, align="right"),
    Column("deposits", 400, 500, align="right"),
    Column("balance", 500, 560, align="right"),
]

MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

TITLE_RE = re.compile(r"Account Transaction Details")
ACCOUNT_NUMBER_RE = re.compile(r"(\d{3}-\d{3}-\d{3}-\d)")
PERIOD_RE = re.compile(r"Period:\s*(\d{2} \w{3} \d{4}) to (\d{2} \w{3} \d{4})")
DATE_RE = re.compile(r"^(\d{2}) (\w{3})$")


def _parse_amount(text: str) -> float | None:
    text = text.strip()
    if not text:
        return None
    return float(text.replace(",", ""))


def _month_year_map(first_page_text: str) -> dict[int, int]:
    m = PERIOD_RE.search(first_page_text)
    if not m:
        return {}
    start = m.group(1).split()
    end = m.group(2).split()
    start_month, start_year = MONTHS[start[1]], int(start[2])
    end_month, end_year = MONTHS[end[1]], int(end[2])
    return {start_month: start_year, end_month: end_year}


def _find_title_and_header(lines) -> tuple[int, int]:
    """Locate the 'Account Transaction Details' title line and the
    'Date Description Withdrawals Deposits Balance' column-header line."""
    title_idx = next((i for i, l in enumerate(lines) if TITLE_RE.search(l.text())), None)
    header_idx = next(
        (i for i, l in enumerate(lines) if "Date" in l.text() and "Withdrawals" in l.text()),
        None,
    )
    if title_idx is None or header_idx is None:
        raise ValueError("Could not locate 'Account Transaction Details' table header")
    return title_idx, header_idx


def _account_identity(lines, title_idx: int, header_idx: int) -> tuple[str, str]:
    identity_text = " ".join(l.text() for l in lines[title_idx + 1 : header_idx])
    identity_text = identity_text.replace("(continued)", "").strip()
    m = ACCOUNT_NUMBER_RE.search(identity_text)
    if not m:
        raise ValueError("Could not locate account number")
    account_number = m.group(1)
    account_type = identity_text[: m.start()].strip()
    return account_type, account_number


def parse(pages) -> ParsedStatement:
    tx_pages = [p for p in pages if TITLE_RE.search(p.extract_text() or "")]
    if not tx_pages:
        raise ValueError("No 'Account Transaction Details' pages found")

    month_year = _month_year_map(pages[0].extract_text() or "")
    default_year = max(month_year.values()) if month_year else None

    account_type = None
    account_number = None
    transactions: list[ParsedTransaction] = []
    current: ParsedTransaction | None = None

    for page in tx_pages:
        words = [w for w in extract_words(page) if w.top < FOOTER_TOP_CUTOFF]
        lines = group_into_lines(words)
        title_idx, header_idx = _find_title_and_header(lines)

        if account_type is None:
            account_type, account_number = _account_identity(lines, title_idx, header_idx)

        for line in lines[header_idx + 1 :]:
            text = line.text()
            row = bucket_line(line, COLUMNS)
            date_text = row["date"].strip()
            desc_text = row["description"].strip()

            if not date_text and not desc_text:
                continue  # SGD sub-header row, footer boilerplate, etc.

            if "(continued)" in text:
                # Repeated "<account type> <account number> (continued)" identity
                # line real UOB statements print at the top of continuation pages.
                # It has no date, so without this it gets mistaken for a
                # description-continuation line and appended onto whatever
                # transaction was last open across the page break (see CLAUDE.md).
                continue

            if "BALANCE B/F" in text or text.strip().startswith("Total"):
                if current is not None:
                    transactions.append(current)
                current = None
                continue

            day_match = DATE_RE.match(date_text)
            if day_match:
                if current is not None:
                    transactions.append(current)
                day, mon_abbr = day_match.groups()
                month = MONTHS.get(mon_abbr)
                year = month_year.get(month, default_year)
                iso_date = f"{year:04d}-{month:02d}-{int(day):02d}"

                withdrawal = _parse_amount(row["withdrawals"])
                deposit = _parse_amount(row["deposits"])
                amount = -withdrawal if withdrawal is not None else (deposit or 0.0)
                balance = _parse_amount(row["balance"])

                current = ParsedTransaction(
                    transaction_date=iso_date,
                    raw_description=desc_text,
                    amount=amount,
                    balance=balance,
                )
            elif current is not None and desc_text:
                current.raw_description += " " + desc_text

    if current is not None:
        transactions.append(current)

    digits = re.sub(r"\D", "", account_number)
    account = ParsedAccount(
        bank_name="UOB",
        account_number=account_number,
        account_number_masked="••" + digits[-4:],
        account_type=account_type,
        transactions=transactions,
    )
    return ParsedStatement(bank_name="UOB", accounts=[account])
