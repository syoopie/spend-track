from app.localization import ACTIVE_COUNTRY
from app.parsing.base import BankParser, ParsedStatement, UnparseableStatementError

# Ordered list of registered per-bank parsing engines, sourced from the
# active country's profile - adding a new bank there (or a second country)
# is what changes this list, not an edit here.
PARSERS: list[BankParser] = ACTIVE_COUNTRY.bank_parsers


def detect_and_parse(pages: list) -> ParsedStatement:
    for parser in PARSERS:
        if parser.detect(pages):
            return parser.parse(pages)
    bank_names = ", ".join(p.bank_name for p in PARSERS if p.parsing_implemented)
    raise UnparseableStatementError(f"Could not identify the statement's bank (expected {bank_names}).")
