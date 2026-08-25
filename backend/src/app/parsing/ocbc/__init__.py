from app.parsing.base import BankParser, ParsedStatement, UnparseableStatementError


class OCBCParser(BankParser):
    """Stub: no OCBC sample statements were available to build a real parser
    against. See dbs/__init__.py for the same rationale."""

    bank_name = "OCBC"
    parsing_implemented = False

    def detect(self, pages: list) -> bool:
        if not pages:
            return False
        text = pages[0].extract_text() or ""
        return "OCBC Bank" in text or "Oversea-Chinese Banking" in text

    def parse(self, pages: list) -> ParsedStatement:
        raise UnparseableStatementError(
            "OCBC statement detected, but OCBC parsing is not yet implemented "
            "(no sample statements were available to build against)."
        )
