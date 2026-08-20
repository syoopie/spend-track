from app.parsing.base import BankParser, ParsedStatement, UnparseableStatementError
from app.parsing.uob import account_statement, card_statement


class UOBParser(BankParser):
    bank_name = "UOB"

    def detect(self, pages: list) -> bool:
        if not pages:
            return False
        text = pages[0].extract_text() or ""
        return "United Overseas Bank" in text

    def parse(self, pages: list) -> ParsedStatement:
        first_text = pages[0].extract_text() or ""
        if "Statement of Account" in first_text:
            return account_statement.parse(pages)
        if "Credit Card(s) Statement" in first_text:
            return card_statement.parse(pages)
        raise UnparseableStatementError(
            "Recognized a UOB statement but not its subtype (expected "
            "'Statement of Account' or 'Credit Card(s) Statement')"
        )
