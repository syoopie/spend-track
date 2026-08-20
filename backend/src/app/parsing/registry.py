from app.parsing.base import BankParser, ParsedStatement, UnparseableStatementError
from app.parsing.dbs import DBSParser
from app.parsing.ocbc import OCBCParser
from app.parsing.uob import UOBParser

# Ordered list of registered per-bank parsing engines. Adding a new bank is a
# matter of implementing BankParser and appending it here - nothing else in
# the ingestion pipeline needs to change.
PARSERS: list[BankParser] = [UOBParser(), DBSParser(), OCBCParser()]


def detect_and_parse(pages: list) -> ParsedStatement:
    for parser in PARSERS:
        if parser.detect(pages):
            return parser.parse(pages)
    raise UnparseableStatementError(
        "Could not identify the statement's bank (expected DBS, OCBC, or UOB)."
    )
