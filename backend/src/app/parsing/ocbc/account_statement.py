"""OCBC deposit-account statement (`Statement of Account`).

Layout: Date | Value Date | Description | Withdrawal | Deposit | Balance.
The value-date column is the one real difference from DBS - some OCBC
templates print it and some don't, so it is declared optional and the
neighbouring column boundaries close over its absence.

`BALANCE B/F` opens the table and `BALANCE C/F` closes it; transaction dates
print as `03 OCT` with no year.
"""

import re

from app.parsing.base import ParsedStatement
from app.parsing.columnar import AccountSpec, TableSpec, parse_table
from app.parsing.pdf_utils import HeaderColumn

SPEC = TableSpec(
    bank_name="OCBC",
    header=[
        HeaderColumn("date", ("transaction date", "date")),
        HeaderColumn("value_date", ("value date",), optional=True),
        HeaderColumn("description", ("description",)),
        HeaderColumn("withdrawal", ("withdrawal", "withdrawals"), align="right"),
        HeaderColumn("deposit", ("deposit", "deposits"), align="right"),
        HeaderColumn("balance", ("balance",), align="right"),
    ],
    account=AccountSpec(
        # OCBC prints account numbers flat (`501234567001`) or grouped
        # (`501-234567-001`).
        number_pattern=re.compile(r"\b(\d{3}-\d{6}-\d{3}|\d{9,12})\b"),
        name_stopwords=("statement of account", "account details", "singapore dollar", "currency"),
        fallback_name="OCBC Account",
    ),
    statement_date_pattern=re.compile(
        r"(?:as at|Statement Date|Period[^\n]*to)\D{0,12}(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{4})",
        re.I,
    ),
    skip_prefixes=(
        "BALANCE B/F",
        "BALANCE C/F",
        "BALANCE BROUGHT FORWARD",
        "BALANCE CARRIED FORWARD",
        "Total",
        "CURRENCY",
    ),
    closing_balance_prefix="BALANCE C/F",
    totals_prefix="Total",
    account_type_label="OCBC Account",
)


def parse(pages) -> ParsedStatement:
    return parse_table(pages, SPEC)
