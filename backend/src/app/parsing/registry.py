from app.localization import ACTIVE_COUNTRY
from app.parsing.base import BankParser, ParsedStatement, UnparseableStatementError

# Ordered list of registered per-bank parsing engines, sourced from the
# active country's profile - adding a new bank there (or a second country)
# is what changes this list, not an edit here.
PARSERS: list[BankParser] = ACTIVE_COUNTRY.bank_parsers


def detect_and_parse(pages: list, parsers: list[BankParser] | None = None) -> ParsedStatement:
    """Hand `pages` to the first registered parser that recognizes them.

    `parsers` overrides the registered list, so a test can exercise the
    dispatch and error wording against a parser that isn't shipped (a stub for
    a bank nobody has written yet, say) without registering it for real users.
    """
    parsers = PARSERS if parsers is None else parsers
    for parser in parsers:
        if parser.detect(pages):
            return parser.parse(pages)
    bank_names = ", ".join(p.bank_name for p in parsers if p.parsing_implemented)
    raise UnparseableStatementError(f"Could not identify the statement's bank (expected {bank_names}).")
