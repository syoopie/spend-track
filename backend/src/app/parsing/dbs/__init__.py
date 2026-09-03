from app.parsing.base import BankParser, ParsedStatement, UnparseableStatementError
from app.parsing.dbs import account_statement, card_statement

#: Text that only ever appears on a card statement, used to pick the subtype.
#: Checked before the deposit-account anchors because a card statement also
#: says "Statement of Account" on some templates, while a deposit statement
#: never prints a previous balance or a minimum payment.
CARD_ANCHORS = (
    "PREVIOUS BALANCE",
    "MINIMUM PAYMENT",
    "Minimum Payment",
    "Credit Card Statement",
    "CREDIT CARD STATEMENT",
)

ACCOUNT_ANCHORS = (
    "Balance Brought Forward",
    "BALANCE BROUGHT FORWARD",
    "Statement of Account",
    "STATEMENT OF ACCOUNT",
    "Account Details",
)


class DBSParser(BankParser):
    """DBS and POSB (one bank, two brands, one statement template).

    Built from the published layout rather than from real statements - see
    `parsing/columnar.py` for what that changes, and docs/adding-a-bank.md for
    how to send a sanitized statement if this parser gets your format wrong.
    """

    bank_name = "DBS"

    def detect(self, pages: list) -> bool:
        if not pages:
            return False
        text = "\n".join(page.extract_text() or "" for page in pages[:2])
        # A real DBS consolidated eStatement never prints "DBS Bank" on the
        # cover, and a sanitized sample keeps only the words a parser reads -
        # so identity rests on "DBS" plus a furniture row DBS phrases its own
        # way ("Balance Brought/Carried Forward", where UOB and OCBC say
        # "BALANCE B/F"). "DBS Bank" and "POSB" still catch the card
        # statements; "PDS_MMCON" is the document code on a real one's footer.
        if "DBS Bank" in text or "POSB" in text or "PDS_MMCON" in text:
            return True
        return "DBS" in text and (
            "Balance Brought Forward" in text
            or "Balance Carried Forward" in text
            or "Statement of Account" in text
        )

    def parse(self, pages: list) -> ParsedStatement:
        text = "\n".join(page.extract_text() or "" for page in pages[:2])
        if any(anchor in text for anchor in CARD_ANCHORS):
            return card_statement.parse(pages)
        if any(anchor in text for anchor in ACCOUNT_ANCHORS):
            return account_statement.parse(pages)
        raise UnparseableStatementError(
            "Recognized a DBS/POSB statement but not its subtype (expected a deposit "
            "account statement or a credit card statement)."
        )
