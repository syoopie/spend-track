from app.parsing.base import BankParser, ParsedStatement, UnparseableStatementError


class DBSParser(BankParser):
    """Stub: no DBS sample statements were available to build a real parser
    against. Detection is implemented so the API can report a precise
    "DBS detected but not yet supported" error rather than a generic
    unrecognized-format one; parsing itself is a drop-in for later."""

    bank_name = "DBS"

    def detect(self, pages: list) -> bool:
        if not pages:
            return False
        text = pages[0].extract_text() or ""
        return "DBS Bank" in text or "POSB" in text

    def parse(self, pages: list) -> ParsedStatement:
        raise UnparseableStatementError(
            "DBS statement detected, but DBS parsing is not yet implemented "
            "(no sample statements were available to build against)."
        )
