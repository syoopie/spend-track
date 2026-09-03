"""A spec-driven engine for the two statement shapes every bank here prints.

`parsing/uob/` is hand-written: its column x-ranges were measured off real UOB
statements, and its quirks (the bilingual footer, the Summary-table
false-positive) were found by running it against those statements. Nothing
about that is worth generalizing away, and rewriting it onto this engine with
no real statement to re-validate against would trade tested code for untested
code.

DBS and OCBC are the opposite case. Their layouts are known - both print the
same two tables every retail bank prints - but no real statement was available
to calibrate against, so their parsers are declarative specs over this engine
rather than another two hand-tuned copies of the UOB code. Two consequences
that matter:

* Column ranges come from `columns_from_header`, read off the header row at
  parse time, so nothing here depends on an x-coordinate nobody measured.
* Every parse ends in `_reconcile`, which checks the transactions against a
  figure the statement itself prints. A parser built without a real sample to
  test on is exactly the parser that should refuse to return numbers it cannot
  prove, rather than quietly importing a wrong balance.

See docs/adding-a-bank.md for what a new bank has to fill in.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.parsing.base import ParsedAccount, ParsedStatement, ParsedTransaction, UnparseableStatementError
from app.parsing.pdf_utils import HeaderColumn, Line, bucket_line, columns_from_header, extract_words, group_into_lines

MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

#: "01 Oct", "01 OCT" - a day and a month abbreviation, no year.
DAY_MONTH_RE = re.compile(r"^(\d{1,2})\s+([A-Za-z]{3})$")
#: "02/07" - day and month as numbers, no year (OCBC card statements).
DAY_MONTH_NUMERIC_RE = re.compile(r"^(\d{1,2})/(\d{1,2})$")
#: "01/12/2023" - a fully-specified date (DBS deposit statements print the year).
DAY_MONTH_YEAR_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
#: Text that labels an account number rather than naming the account.
LABEL_ONLY_RE = re.compile(r"^(account|card|a/c)\s*(no\.?|number)?\s*[:.]?$", re.I)
#: A trailing "... Account No." label on an inline heading, to strip off the name.
LABEL_SUFFIX_RE = re.compile(r"\s*(account|card|a/c)\s*(no\.?|number)?\s*[:.]?\s*$", re.I)
#: A bare money figure, optionally thousands-separated, optionally CR/DR-suffixed.
MONEY_RE = re.compile(r"^(?P<sign>-)?(?P<value>\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)\s*(?P<polarity>CR|DR)?$", re.I)


class StatementReconciliationError(UnparseableStatementError):
    """The statement parsed, but its transactions don't add up to a total the
    statement itself prints.

    This is deliberately fatal rather than a warning. The failure mode it
    guards against - a column boundary landing a few points off, so some
    amounts are dropped or read into the wrong column - produces a plausible
    looking import with wrong numbers, which is far worse than a refused one.
    """


def parse_money(text: str) -> float | None:
    """Parse one column's worth of text as money, or None if it isn't money.

    Strictness is the point: a description that overflows its column and
    spills into an amount column must be rejected here rather than
    contributing a garbage figure.
    """
    match = MONEY_RE.match(text.strip())
    if not match:
        return None
    value = float(match.group("value").replace(",", ""))
    if match.group("sign") or (match.group("polarity") or "").upper() == "DR":
        value = -value
    return value


def parse_day_month(text: str) -> tuple[int, int] | None:
    """Parse "01 Oct" or "02/07" into (day, month), or None."""
    if match := DAY_MONTH_RE.match(text.strip()):
        day, month_abbr = match.groups()
        month = MONTHS.get(month_abbr.upper())
        return (int(day), month) if month else None
    if match := DAY_MONTH_NUMERIC_RE.match(text.strip()):
        day, month = (int(g) for g in match.groups())
        return (day, month) if 1 <= month <= 12 else None
    return None


def parse_row_date(text: str) -> tuple[int, int, int | None] | None:
    """Parse a transaction row's date into (day, month, year-or-None).

    A year of None means the row printed none and it must be resolved from the
    statement date (`YearResolver`) - the UOB and OCBC case. DBS deposit rows
    print the year in full ("01/12/2023"), so it is carried through directly
    and the statement date is not consulted for that row.
    """
    text = text.strip()
    if match := DAY_MONTH_YEAR_RE.match(text):
        day, month, year = (int(g) for g in match.groups())
        return (day, month, year) if 1 <= month <= 12 else None
    day_month = parse_day_month(text)
    return (day_month[0], day_month[1], None) if day_month is not None else None


@dataclass(frozen=True)
class YearResolver:
    """Turns a year-less transaction date into an ISO date.

    Statements print the statement date in full but transaction dates without
    a year, so a statement dated 05 Jan carrying a 28 Dec transaction means the
    *previous* December. The rule is the same one `uob/card_statement.py` uses:
    a month later than the statement's own month belongs to the year before.
    """

    statement_year: int
    statement_month: int

    def iso(self, day: int, month: int) -> str:
        year = self.statement_year - 1 if month > self.statement_month else self.statement_year
        return f"{year:04d}-{month:02d}-{day:02d}"


@dataclass(frozen=True)
class AccountSpec:
    """How to recognize an account/card section heading above a table header.

    `number_pattern` matches the account or card number; `name_stopwords` are
    lines that are never the account's name (a page heading, a currency
    sub-header) so the name search can walk past them.
    """

    number_pattern: re.Pattern[str]
    name_stopwords: tuple[str, ...] = ()
    fallback_name: str = "Account"


@dataclass(frozen=True)
class TableSpec:
    """Everything bank-specific about one statement table."""

    bank_name: str
    #: Ordered left-to-right. Must include a "description" column, and either
    #: "withdrawal"+"deposit" (a deposit account) or "amount" (a credit card).
    header: list[HeaderColumn]
    account: AccountSpec
    #: Anchor giving the statement's own date, for year resolution. Group 1 =
    #: day, group 2 = month abbreviation or number, group 3 = year.
    statement_date_pattern: re.Pattern[str]
    #: Description prefixes that are table furniture, not transactions.
    skip_prefixes: tuple[str, ...] = ()
    #: Description prefix of the row carrying the statement's closing balance,
    #: used by the reconciliation check.
    closing_balance_prefix: str | None = None
    #: Description prefix of the row carrying the withdrawal/deposit totals.
    totals_prefix: str | None = None
    is_card: bool = False
    #: Text below this y-coordinate is page footer, dropped before grouping
    #: words into lines - see CLAUDE.md on UOB's bilingual disclaimer, which
    #: lands inside the description column's x-range.
    footer_top_cutoff: float = 780.0


@dataclass
class _Section:
    """One account's table, accumulated across however many pages it spans."""

    account: ParsedAccount
    transactions: list[ParsedTransaction] = field(default_factory=list)
    current: ParsedTransaction | None = None
    closing_balance: float | None = None
    printed_withdrawals: float | None = None
    printed_deposits: float | None = None

    def close(self) -> None:
        if self.current is not None:
            self.transactions.append(self.current)
            self.current = None


def parse_table(pages, spec: TableSpec) -> ParsedStatement:
    """Extract every account section in `pages` according to `spec`."""
    resolver = _statement_date(pages, spec)

    sections: dict[str, _Section] = {}
    order: list[str] = []
    current: _Section | None = None

    for page in pages:
        words = [
            w
            for w in extract_words(page)
            # Rotated text (a DBS consolidated statement prints its legal-entity
            # block as a vertical strip down the left margin) shares `top`
            # coordinates with the transaction rows and would otherwise merge
            # into them. It is never table data.
            if w.upright and w.top < spec.footer_top_cutoff
        ]
        lines = group_into_lines(words)

        # A page can carry more than one table: a DBS consolidated statement
        # prints every account you hold, one section after another, and a
        # multi-card statement does the same per card. Taking only the first
        # header on the page would silently pour the second section's rows
        # into the first section's account.
        headers = _find_headers(lines, spec, page.width)
        for position, (header_idx, columns) in enumerate(headers):
            identity = _account_identity(lines, header_idx, spec)
            if identity is None and current is None:
                continue  # a table we can't attribute to an account is not importable
            if identity is not None:
                number, name = identity
                if number not in sections:
                    sections[number] = _Section(account=_new_account(number, name, spec))
                    order.append(number)
                if current is not None and current is not sections[number]:
                    current.close()
                current = sections[number]

            assert current is not None
            for line in lines[header_idx + 1 : _section_end(lines, headers, position, spec)]:
                _consume_row(line, columns, spec, resolver, current)

    for section in sections.values():
        section.close()

    if not order:
        raise UnparseableStatementError(
            f"Recognized a {spec.bank_name} statement but found no "
            f"'{' / '.join(c.name for c in spec.header)}' transaction table in it."
        )

    accounts = []
    for number in order:
        section = sections[number]
        _reconcile(section, spec)
        if not section.transactions:
            # A consolidated DBS statement lists every account you hold, and a
            # dormant one (a $1 SRS account, say) prints its heading and an
            # empty table. There is nothing to import from it, and emitting a
            # transaction-less account would just be clutter downstream.
            continue
        section.account.transactions = section.transactions
        accounts.append(section.account)

    if not accounts:
        raise UnparseableStatementError(
            f"Recognized a {spec.bank_name} statement but found no transactions in any "
            "of its account sections."
        )
    return ParsedStatement(bank_name=spec.bank_name, accounts=accounts)


def _new_account(number: str, name: str, spec: TableSpec) -> ParsedAccount:
    digits = re.sub(r"\D", "", number)
    return ParsedAccount(
        bank_name=spec.bank_name,
        account_number=number,
        account_number_masked="••" + digits[-4:],
        account_type=name,
        is_card=spec.is_card,
    )


def _statement_date(pages, spec: TableSpec) -> YearResolver:
    for page in pages[:2]:  # the anchor is always on the cover or first table page
        match = spec.statement_date_pattern.search(page.extract_text() or "")
        if not match:
            continue
        month_text, year = match.group(2), match.group(3)
        month = MONTHS.get(month_text.upper()) if not month_text.isdigit() else int(month_text)
        if month:
            return YearResolver(statement_year=int(year), statement_month=month)
    raise UnparseableStatementError(
        f"Recognized a {spec.bank_name} statement but could not find its statement date, "
        "which every transaction's year is derived from (transaction rows print no year)."
    )


def _find_headers(lines: list[Line], spec: TableSpec, page_width: float) -> list[tuple[int, list]]:
    found = []
    for idx, line in enumerate(lines):
        columns = columns_from_header(line, spec.header, page_width)
        if columns is not None:
            found.append((idx, columns))
    return found


def _section_end(lines: list[Line], headers: list[tuple[int, list]], position: int, spec: TableSpec) -> int:
    """Where this section's rows stop.

    Not at the next table header but at the *heading* above it - the account
    name, number and currency lines introducing the next section sit between
    the two, and they carry no date, so a section that ran all the way to the
    next header would append them to its own last transaction's description.
    """
    if position + 1 >= len(headers):
        return len(lines)
    header_idx = headers[position][0]
    next_header_idx = headers[position + 1][0]
    identity_idx = _identity_line_index(lines, next_header_idx, spec)
    # The backward search can walk past the next header entirely - if the next
    # table has no heading of its own (a continuation of the same account, say)
    # it finds *this* section's identity line instead, which sits before this
    # header. Ending there would make the row range empty and lose the whole
    # section without a word about it, so fall back to the next header.
    if identity_idx is None or identity_idx <= header_idx:
        return next_header_idx
    return identity_idx


def _identity_line_index(lines: list[Line], header_idx: int, spec: TableSpec) -> int | None:
    """Index of the line above `header_idx` carrying the account/card number.

    Searched *backwards* from the header, never forwards from the top of the
    page, for the reason CLAUDE.md records for UOB card statements: the same
    number also appears in a summary table further up, under a different (and
    wrong) name.
    """
    for back in range(header_idx - 1, -1, -1):
        if spec.account.number_pattern.search(lines[back].text()):
            return back
    return None


def _account_identity(lines: list[Line], header_idx: int, spec: TableSpec) -> tuple[str, str] | None:
    """Find the account/card number and name in the lines above the table header."""
    back = _identity_line_index(lines, header_idx, spec)
    if back is not None:
        text = lines[back].text()
        match = spec.account.number_pattern.search(text)
        assert match is not None
        number = match.group(1)
        name = text[: match.start()].strip(" :-•")
        # A real DBS heading is one line: "DBS Multiplier Account Account No.
        # 120-752744-8" - strip the trailing "Account No." label so the name
        # is just the account type.
        name = LABEL_SUFFIX_RE.sub("", name).strip(" :-•")
        if not name or LABEL_ONLY_RE.match(name):
            # The number's own line reads "Account No. 123-456789-0" - a label,
            # not a name. The account's name is the heading printed above it.
            name = _name_above(lines, back, spec)
        return number, name or spec.account.fallback_name
    return None


def _name_above(lines: list[Line], idx: int, spec: TableSpec) -> str:
    for back in range(idx - 1, max(idx - 4, -1), -1):
        candidate = lines[back].text().strip()
        if not candidate:
            continue
        if any(stop.lower() in candidate.lower() for stop in spec.account.name_stopwords):
            continue
        if spec.account.number_pattern.search(candidate):
            continue
        return candidate
    return ""


def _consume_row(line: Line, columns, spec: TableSpec, resolver: YearResolver, section: _Section) -> None:
    row = bucket_line(line, columns)
    description = row.get("description", "").strip()
    date_text = row.get("date", "").strip()

    if not description and not date_text:
        return  # a currency sub-header, a rule, stray footer text

    for prefix in spec.skip_prefixes:
        if description.upper().startswith(prefix.upper()):
            section.close()
            _capture_printed_totals(description, row, spec, section)
            return

    parsed_date = parse_row_date(date_text) if date_text else None
    if parsed_date is not None:
        section.close()
        day, month, year = parsed_date
        iso = f"{year:04d}-{month:02d}-{day:02d}" if year is not None else resolver.iso(day, month)
        section.current = ParsedTransaction(
            transaction_date=iso,
            raw_description=description,
            amount=_row_amount(row),
            balance=parse_money(row.get("balance", "")),
        )
    elif section.current is not None and description:
        # A continuation line: real statements wrap long PayNow/GIRO details
        # onto the next row with the date column left empty.
        section.current.raw_description += " " + description


def _row_amount(row: dict[str, str]) -> float:
    """Signed amount for one row: negative is money out, positive is money in."""
    if "amount" in row:
        # Card statements print one column; a credit is suffixed CR.
        value = parse_money(row["amount"])
        if value is None:
            return 0.0
        text = row["amount"].strip().upper()
        return value if text.endswith("CR") else -abs(value)
    withdrawal = parse_money(row.get("withdrawal", ""))
    deposit = parse_money(row.get("deposit", ""))
    if withdrawal is not None:
        return -abs(withdrawal)
    return abs(deposit) if deposit is not None else 0.0


def _capture_printed_totals(description: str, row: dict[str, str], spec: TableSpec, section: _Section) -> None:
    """Remember the figures the statement prints for itself, for `_reconcile`."""
    upper = description.upper()
    if spec.closing_balance_prefix and upper.startswith(spec.closing_balance_prefix.upper()):
        # A closing-balance row prints its figure in the balance column on
        # deposit statements and in the amount column on card statements.
        section.closing_balance = parse_money(row.get("balance", "")) or parse_money(row.get("amount", ""))
    if spec.totals_prefix and upper.startswith(spec.totals_prefix.upper()):
        section.printed_withdrawals = parse_money(row.get("withdrawal", ""))
        section.printed_deposits = parse_money(row.get("deposit", ""))


def _reconcile(section: _Section, spec: TableSpec) -> None:
    """Check the parse against a figure the statement prints for itself.

    Only checks what the statement actually printed - a statement carrying
    neither a totals row nor a closing balance is imported unchecked, because
    refusing it would reject a perfectly good statement over a missing row.
    """
    transactions = section.transactions
    if not transactions:
        return

    withdrawals = round(sum(-t.amount for t in transactions if t.amount < 0), 2)
    deposits = round(sum(t.amount for t in transactions if t.amount > 0), 2)

    if section.printed_withdrawals is not None and abs(section.printed_withdrawals - withdrawals) > 0.01:
        raise StatementReconciliationError(
            f"{spec.bank_name} statement did not reconcile: the statement prints total withdrawals of "
            f"{section.printed_withdrawals:,.2f} but the transactions read from it sum to {withdrawals:,.2f}. "
            "Refusing to import rather than risk wrong figures - please report this statement's layout."
        )
    if section.printed_deposits is not None and abs(section.printed_deposits - deposits) > 0.01:
        raise StatementReconciliationError(
            f"{spec.bank_name} statement did not reconcile: the statement prints total deposits of "
            f"{section.printed_deposits:,.2f} but the transactions read from it sum to {deposits:,.2f}. "
            "Refusing to import rather than risk wrong figures - please report this statement's layout."
        )

    final_balance = transactions[-1].balance
    if section.closing_balance is not None and final_balance is not None:
        if abs(section.closing_balance - final_balance) > 0.01:
            raise StatementReconciliationError(
                f"{spec.bank_name} statement did not reconcile: the statement's closing balance is "
                f"{section.closing_balance:,.2f} but the last transaction read from it leaves "
                f"{final_balance:,.2f}. Refusing to import rather than risk wrong figures - "
                "please report this statement's layout."
            )
