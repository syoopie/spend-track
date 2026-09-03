"""DBS / POSB deposit-account statement (the consolidated eStatement).

Layout, left to right: Date | Description | Withdrawal (-) | Deposit (+) |
Balance. `CURRENCY: SINGAPORE DOLLAR` is a sub-header between the account
heading and the column header. Each page opens with `Balance Brought Forward
SGD <n>` and closes with `Balance Carried Forward SGD <n>`; neither is a
transaction. The account section as a whole ends with one
`Total Balance Carried Forward in SGD: <withdrawals> <deposits> <balance>`
row, which is what the reconciliation check reads.

Transaction dates print in full ("01/12/2023"), so the year is taken straight
from the row rather than resolved from the statement date.

A consolidated eStatement carries every account you hold, each as its own
heading + table (several to a page), which is why the engine keys sections by
account number. A dormant account prints its heading over an empty table; the
engine drops a section with no transactions.
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
        # (`123-456789-0`, `120-752744-8`), the SRS four-group form
        # (`0120-149295-5-223`), and flat (10-12 digits).
        number_pattern=re.compile(r"\b(\d{3,4}-\d-\d{6}|\d{3,4}-\d{5,6}-\d(?:-\d{3})?|\d{10,12})\b"),
        name_stopwords=(
            "currency", "singapore dollar", "statement of account", "account details",
            "transaction details", "account summary", "deposits",
            "supplementary retirement scheme",
        ),
        fallback_name="DBS Account",
    ),
    statement_date_pattern=re.compile(
        r"(?:as at|Statement Date|Period[^\n]*to)\D{0,12}(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{4})",
        re.I,
    ),
    skip_prefixes=(
        "Balance Brought Forward",
        "Balance Carried Forward",
        "Total Balance Carried Forward",
        "Total",
        "CURRENCY",
        "SINGAPORE DOLLAR",
    ),
    closing_balance_prefix="Total Balance Carried Forward",
    totals_prefix="Total Balance Carried Forward",
)


def parse(pages) -> ParsedStatement:
    return parse_table(pages, SPEC)
