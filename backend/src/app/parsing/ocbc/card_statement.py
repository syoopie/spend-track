"""OCBC credit card statement.

Built against two real statements (`PDF Examples/OCBC/Card Statements/`), so
the layout notes here are measured, not guessed:

* The table header is `TRANSACTION DATE | DESCRIPTION | AMOUNT (SGD)`. Dates
  print numerically and year-less (`02/07` = 2 July), unlike DBS and UOB's
  `05 OCT`.
* The card heading sits *below* the header, not above it - the header, then
  the card product name (`OCBC INFINITY CASHBACK`), then the card number
  (often masked, or absent entirely), then `LAST MONTH'S BALANCE`. Hence
  `identity_below_header`, and the section is keyed on the product name so a
  statement that omits the number still lands on the same account.
* A credit - the bill payment, a `CASH REBATE` - is bracketed: `(1,133.96)`.
  `columnar.parse_money` reads that as negative and `_row_amount` flips it back
  to a positive (money-in) amount.
* `LAST MONTH'S BALANCE` and `SUBTOTAL` bracket the transactions. The parse is
  reconciled against them: opening balance + charges - credits == SUBTOTAL.
* The statement date appears only in the summary box at the top, which a
  contributor sharing the file redacts wholesale. `allow_dateless` lets the
  parse fall back to resolving each year-less date against today.
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
        number_pattern=re.compile(r"\b([\dxX*]{4}-[\dxX*]{4}-[\dxX*]{4}-[\dxX*]{4})\b"),
        name_stopwords=("statement of account", "summary", "card summary"),
        fallback_name="OCBC Credit Card",
        identity_below_header=True,
    ),
    statement_date_pattern=re.compile(
        r"Statement Date\D{0,15}(\d{1,2})[-/\s]([A-Za-z]{3}|\d{1,2})[-/\s](\d{4})", re.I
    ),
    skip_prefixes=(
        "LAST MONTH'S BALANCE",
        "LAST MONTH’S BALANCE",  # the curly apostrophe OCBC's PDF font emits
        "PREVIOUS BALANCE",
        "SUBTOTAL",
        "SUB TOTAL",
        "TOTAL",
        "NEW BALANCE",
        "MINIMUM PAYMENT",
    ),
    opening_balance_prefix="LAST MONTH'S BALANCE",
    closing_balance_prefix="SUBTOTAL",
    allow_dateless=True,
    is_card=True,
)


def parse(pages) -> ParsedStatement:
    return parse_table(pages, SPEC)
