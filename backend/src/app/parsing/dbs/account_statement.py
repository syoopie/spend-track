"""DBS / POSB deposit-account statement (`Statement of Account`).

Layout, left to right: DATE | DESCRIPTION | WITHDRAWAL | DEPOSIT | BALANCE,
with `Balance Brought Forward` opening the table and `Balance Carried Forward`
closing it, and a `CURRENCY : SINGAPORE DOLLAR` sub-header between the account
heading and the column header. Transaction dates print as `01 Oct` with no
year; the year comes from the statement date.

A consolidated DBS eStatement carries several accounts, each as its own
heading + table, which is why the engine keys sections by account number
instead of assuming one account per document.
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
        HeaderColumn("withdrawal", ("withdrawal", "withdrawals"), align="right"),
        HeaderColumn("deposit", ("deposit", "deposits"), align="right"),
        HeaderColumn("balance", ("balance",), align="right"),
    ],
    account=AccountSpec(
        # DBS and POSB print account numbers in several shapes: grouped
        # (`123-456789-0`, `123-4-567890`) and flat (10-12 digits).
        number_pattern=re.compile(r"\b(\d{3}-\d-\d{6}|\d{3}-\d{5,6}-\d|\d{10,12})\b"),
        name_stopwords=("currency", "singapore dollar", "statement of account", "account details"),
        fallback_name="DBS Account",
    ),
    statement_date_pattern=re.compile(
        r"(?:as at|Statement Date|Period[^\n]*to)\D{0,12}(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{4})",
        re.I,
    ),
    skip_prefixes=(
        "Balance Brought Forward",
        "Balance Carried Forward",
        "Total",
        "CURRENCY",
        "SINGAPORE DOLLAR",
    ),
    closing_balance_prefix="Balance Carried Forward",
    totals_prefix="Total",
    account_type_label="DBS Account",
)


def parse(pages) -> ParsedStatement:
    return parse_table(pages, SPEC)
