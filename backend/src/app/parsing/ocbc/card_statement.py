"""OCBC credit card statement.

Layout: TRANSACTION DATE | DESCRIPTION | AMOUNT (S$), with an optional
posting-date column between the first two. Dates print numerically and
year-less (`02/07` = 2 July), unlike DBS and UOB's `05 OCT`.

`LAST MONTH'S BALANCE` is OCBC's name for the carried-in running balance that
heads the table - the same not-a-transaction row DBS calls PREVIOUS BALANCE.
"""

import re

from app.parsing.base import ParsedStatement
from app.parsing.columnar import AccountSpec, TableSpec, parse_table
from app.parsing.pdf_utils import HeaderColumn

SPEC = TableSpec(
    bank_name="OCBC",
    header=[
        HeaderColumn("date", ("transaction date", "date")),
        HeaderColumn("posting_date", ("posting date",), optional=True),
        HeaderColumn("description", ("description",)),
        HeaderColumn("amount", ("amount",), align="right"),
    ],
    account=AccountSpec(
        number_pattern=re.compile(r"\b([\dxX*]{4}-[\dxX*]{4}-[\dxX*]{4}-\d{4})\b"),
        name_stopwords=("statement of account", "summary", "card summary"),
        fallback_name="OCBC Credit Card",
    ),
    statement_date_pattern=re.compile(
        r"Statement Date\D{0,12}(\d{1,2})[-/\s]([A-Za-z]{3}|\d{1,2})[-/\s](\d{4})", re.I
    ),
    skip_prefixes=(
        "LAST MONTH'S BALANCE",
        "LAST MONTH’S BALANCE",  # the curly apostrophe OCBC's PDF font actually emits
        "PREVIOUS BALANCE",
        "SUB TOTAL",
        "TOTAL",
        "NEW BALANCE",
        "MINIMUM PAYMENT",
    ),
    is_card=True,
    account_type_label="OCBC Credit Card",
)


def parse(pages) -> ParsedStatement:
    return parse_table(pages, SPEC)
