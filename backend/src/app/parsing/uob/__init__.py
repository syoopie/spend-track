from app.parsing.base import BankParser, ParsedStatement, UnparseableStatementError
from app.parsing.uob import account_statement, card_statement


#: Any one of these identifies a UOB statement. The legal name is what the
#: real samples this parser was built from carry on page 1, but it is not the
#: only thing UOB prints: account and credit card statements are rendered by
#: different pipelines (down to different PDF versions), and a variant whose
#: cover page carries only the contact email would otherwise come back as an
#: unrecognized format rather than as a UOB statement this parser can read.
DETECT_ANCHORS = (
    "United Overseas Bank",
    "uobgroup.com",  # covers both card.centre@ and customer.service@
)


class UOBParser(BankParser):
    bank_name = "UOB"

    def detect(self, pages: list) -> bool:
        # Two pages, not one: on some statements the first page is a cover
        # sheet and the identifying text sits on the page after it.
        text = "\n".join(page.extract_text() or "" for page in pages[:2])
        return any(anchor in text for anchor in DETECT_ANCHORS)

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
