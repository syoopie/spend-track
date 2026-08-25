"""Singapore PayNow transfer detection - a payment scheme, not a merchant.

Deliberately its own module (mirroring engine/card_payments.py's pattern)
rather than a private helper buried in rules.py: PayNow transfers are
identified by scheme-specific markers in the description text ("PAYNOW",
the FAST-network reference prefix "PIB"), not by matching a merchant/
keyword like every other categorization rule - a structurally different
kind of signal, so it gets its own name and file instead of blending into
the generic rule-matching code.

"Paynow" (sent) and "Paynow Received" (money in) are the only two
categories in the app that a static rule pattern never targets directly
(see engine/default_rules.py's docstring) - they're always derived here,
either from this module's own marker check or from a matched contact,
because a PayNow line's "match text" is a free-text payee name off
someone's registration rather than an established brand string.
"""

from app.engine.naming import extract_display_name

PAYNOW_MARKERS = ("PAYNOW", "PIB")

CATEGORY_SENT = "Paynow"
CATEGORY_RECEIVED = "Paynow Received"


def is_paynow_transfer(desc_upper: str) -> bool:
    return any(marker in desc_upper for marker in PAYNOW_MARKERS)


def is_paynow_category(category: str) -> bool:
    return category in (CATEGORY_SENT, CATEGORY_RECEIVED)


def category_for_direction(amount: float) -> str:
    return CATEGORY_RECEIVED if amount > 0 else CATEGORY_SENT


def label(raw_description: str, amount: float) -> str:
    direction_word = "from" if amount > 0 else "to"
    return f"PayNow {direction_word} {extract_display_name(raw_description)}"


def contact_label(name: str, amount: float) -> str:
    direction_word = "from" if amount > 0 else "to"
    return f"PayNow {direction_word} {name}"
