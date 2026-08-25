"""Detects the two halves of a credit card bill payment.

One half sits on a deposit/current account statement (the GIRO line paying
the bill); the other sits on the card statement itself (the credit that
settles the balance). Each is excluded from totals for its own reason - see
the two functions below.

Half one: "pay my credit card bill" on a deposit/current account statement.

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


# Half two: the same payment as it appears on the card's own statement - a
# credit that reduces the balance. Left alone, it counts as *inflow*: the
# outflow side is already handled above, but the money coming back to settle
# the card was never income, so a year of card statements would otherwise
# report every bill payment as earnings. Narrower than the markers above on
# purpose - a card statement's other credits (refunds, reversals, cashback,
# rebates) are real and must keep their categories.
CARD_PAYMENT_RECEIVED_MARKERS = (
    # "PAYMT THRU E-BANK/HOMEB/CYBERB" - real UOB card statement text.
    "PAYMT THRU",
    "PYMT THRU",
    "PAYMENT THRU",
    "PAYMENT - THANK YOU",
    "PAYMENT THANK YOU",
    "THANK YOU FOR YOUR PAYMENT",
    "PAYMENT RECEIVED",
    "CARDMEMBER PAYMENT",
)


def looks_like_payment_received_on_card(desc_upper: str) -> bool:
    """Only meaningful for an inflow posting to a card account - see
    categorize() in rules.py, which checks both before calling this."""
    return any(marker in desc_upper for marker in CARD_PAYMENT_RECEIVED_MARKERS)
