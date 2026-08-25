from app.parsing.base import BankParser, ParsedStatement, UnparseableStatementError
from app.parsing.ocbc import account_statement, card_statement

CARD_ANCHORS = (
    "LAST MONTH'S BALANCE",
    "LAST MONTH’S BALANCE",
    "MINIMUM PAYMENT",
    "Minimum Payment",
    "Credit Card Statement",
    "CREDIT CARD STATEMENT",
)

ACCOUNT_ANCHORS = (
    "BALANCE B/F",
    "Statement of Account",
    "STATEMENT OF ACCOUNT",
    "Account Details",
)


class OCBCParser(BankParser):
    """OCBC. Built from the published layout rather than from real statements -
    see `parsing/columnar.py`, and docs/adding-a-bank.md for how to send a
    sanitized statement if this parser gets your format wrong."""

    bank_name = "OCBC"

    def detect(self, pages: list) -> bool:
        if not pages:
            return False
        text = pages[0].extract_text() or ""
        return "OCBC Bank" in text or "Oversea-Chinese Banking" in text

    def parse(self, pages: list) -> ParsedStatement:
        text = "\n".join(page.extract_text() or "" for page in pages[:2])
        if any(anchor in text for anchor in CARD_ANCHORS):
            return card_statement.parse(pages)
        if any(anchor in text for anchor in ACCOUNT_ANCHORS):
            return account_statement.parse(pages)
        raise UnparseableStatementError(
            "Recognized an OCBC statement but not its subtype (expected a deposit "
            "account statement or a credit card statement)."
        )
