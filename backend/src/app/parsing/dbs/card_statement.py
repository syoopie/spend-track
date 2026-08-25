"""DBS credit card statement.

Layout: DATE | DESCRIPTION | AMOUNT (S$), one signed amount column where a
credit (a payment, a refund) carries a `CR` suffix and everything else is a
charge. `PREVIOUS BALANCE` heads the table and is a running balance carried
in from last month, not a transaction - the same trap `uob/card_statement.py`
documents.

Transaction dates print as `05 OCT`, no year, so a statement dated early
January listing a late-December charge resolves that charge into the previous
year (see `columnar.YearResolver`).
"""

import re

from app.parsing.base import ParsedStatement
from app.parsing.columnar import AccountSpec, TableSpec, parse_table
from app.parsing.pdf_utils import HeaderColumn

SPEC = TableSpec(
    bank_name="DBS",
    header=[
        HeaderColumn("date", ("date",)),
        HeaderColumn("description", ("description",)),
        HeaderColumn("amount", ("amount",), align="right"),
    ],
    account=AccountSpec(
        # Card numbers appear both in full and part-masked (`4111-XXXX-XXXX-1234`).
        number_pattern=re.compile(r"\b([\dxX*]{4}-[\dxX*]{4}-[\dxX*]{4}-\d{4})\b"),
        name_stopwords=("statement of account", "summary", "card summary"),
        fallback_name="DBS Credit Card",
    ),
    statement_date_pattern=re.compile(r"Statement Date\D{0,12}(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{4})", re.I),
    skip_prefixes=(
        "PREVIOUS BALANCE",
        "SUB TOTAL",
        "SUB-TOTAL",
        "TOTAL",
        "GRAND TOTAL",
        "NEW BALANCE",
        "MINIMUM PAYMENT",
    ),
    is_card=True,
    account_type_label="DBS Credit Card",
)


def parse(pages) -> ParsedStatement:
    return parse_table(pages, SPEC)
