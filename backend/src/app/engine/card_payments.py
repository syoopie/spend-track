"""Detects "pay my credit card bill" transactions on a deposit/current
account statement.

If the user has also uploaded (or uploads in the same batch) the matching
credit card's own statement, the GIRO/funds-transfer line paying that bill
from the bank account and the individual purchases on the card statement
would otherwise both count as outflow - the same spending counted twice.
This is deliberately a heuristic on description text, not an amount/account
cross-match: real statements rarely embed the card number in the payment
line, so exact pairing isn't reliable. See categorize() in rules.py for how
the two "has a card account" / "is a card account" flags gate this so a
bank-only user (no card statement uploaded) never has real outflow hidden.
"""

CARD_PAYMENT_MARKERS = (
    # "Bill Payment mBK-UOB Cards 4265884081509100" - real UOB account
    # statement text for a GIRO payment settling the user's own UOB card bill.
    "UOB CARDS",
    "CARD CENTRE",
    "CARD CENTER",
    "CREDIT CARD PAYMENT",
    "PAYMENT TO CREDIT CARD",
    "PAYMENT - CREDIT CARD",
    "PAY CREDIT CARD",
    "GIRO CARD PAYMENT",
    "GIRO PAYMENT - CARD",
    "CARD GIRO",
    "CREDIT CARD BILL",
    "CC PAYMENT",
    "CARDMEMBER PAYMENT",
)


def looks_like_card_bill_payment(desc_upper: str) -> bool:
    return any(marker in desc_upper for marker in CARD_PAYMENT_MARKERS)
