"""Priority-ordered categorization rules engine per TECHNICAL_SPEC.md §4.

Rules are evaluated in priority ASC order (priority 1 = highest precedence,
evaluated first); the first matching rule wins - this includes both
user-created rules and the seeded, immutable `is_default` word-bank rules,
which are given a priority far below any user rule so user rules always win
on the same description (see db.py::_seed_default_rules). If no rule
matches, fall back to a contact-identifier match, then to a PayNow-marker
check, then to 'Others'/'Unparsable'. Unmatched rows that look like a
PayNow transfer get their own 'Paynow' category (not 'Others') and are
flagged `needs_review` so the staging UI can highlight them, since a
phone/UEN identifier alone can't tell us who was paid or why.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.engine.card_payments import looks_like_card_bill_payment
from app.engine.naming import extract_display_name

PAYNOW_MARKERS = ("PAYNOW", "PIB")

CARD_PAYMENT_EXCLUSION_REASON = (
    "Credit card bill payment - the actual spending is already counted on the card's own statement"
)


@dataclass
class Categorization:
    category: str
    subcategory: str | None
    contact_id: int | None
    is_excluded: bool
    exclusion_reason: str | None
    needs_review: bool
    matched_label: str | None


def _is_paynow_like(desc_upper: str) -> bool:
    return any(marker in desc_upper for marker in PAYNOW_MARKERS)


def _paynow_direction(amount: float) -> str:
    return "from" if amount > 0 else "to"


def _paynow_label(raw_description: str, amount: float) -> str:
    return f"PayNow {_paynow_direction(amount)} {extract_display_name(raw_description)}"


def find_matching_contact(
    raw_description: str, contact_identifiers: Sequence[Mapping[str, Any]]
) -> Mapping[str, Any] | None:
    """contact_identifiers: rows joining contacts to contact_identifiers,
    each with at least identifier/contact_id/default_category/default_subcategory.
    Matches if the identifier appears verbatim inside the description."""
    for row in contact_identifiers:
        identifier = row["identifier"]
        if identifier and identifier in raw_description:
            return row
    return None


def categorize(
    raw_description: str,
    rules: Sequence[Mapping[str, Any]],
    contact_identifiers: Sequence[Mapping[str, Any]],
    *,
    amount: float = 0.0,
    has_card_account: bool = False,
    posting_account_is_card: bool = False,
) -> Categorization:
    """has_card_account: True if any credit card account is known - already
    committed, or parsed in the same upload batch. posting_account_is_card:
    True if the transaction being categorized itself lives on a card
    account (never auto-excluded as a "pay my card bill" transfer - a card
    can't pay itself). amount: signed transaction amount, used only to pick
    "PayNow from" (incoming, amount > 0) vs "PayNow to" (outgoing) in the
    generated label - defaults to the outgoing phrasing when not given."""
    desc_upper = raw_description.upper()

    for rule in rules:  # must already be sorted by priority ASC
        if rule["match_pattern"].upper() in desc_upper:
            if rule["is_exclusion_rule"]:
                return Categorization(
                    category="Others",
                    subcategory=None,
                    contact_id=None,
                    is_excluded=True,
                    exclusion_reason=rule["exclusion_reason"],
                    needs_review=False,
                    matched_label=None,
                )
            category = rule["target_category"]
            display_label = rule["display_label"] if "display_label" in rule.keys() else None
            label = _paynow_label(raw_description, amount) if category == "Paynow" else (
                display_label or rule["match_pattern"].title()
            )
            return Categorization(
                category=category,
                subcategory=rule["target_subcategory"],
                contact_id=None,
                is_excluded=False,
                exclusion_reason=None,
                needs_review=False,
                matched_label=label,
            )

    if has_card_account and not posting_account_is_card and looks_like_card_bill_payment(desc_upper):
        return Categorization(
            category="Others",
            subcategory=None,
            contact_id=None,
            is_excluded=True,
            exclusion_reason=CARD_PAYMENT_EXCLUSION_REASON,
            needs_review=False,
            matched_label="Credit Card Payment",
        )

    contact = find_matching_contact(raw_description, contact_identifiers)
    if contact is not None:
        category = contact["default_category"]
        name = contact["name"] if "name" in contact.keys() else None
        label = f"PayNow {_paynow_direction(amount)} {name}" if category == "Paynow" and name else name
        return Categorization(
            category=category,
            subcategory=contact["default_subcategory"],
            contact_id=contact["contact_id"],
            is_excluded=False,
            exclusion_reason=None,
            needs_review=False,
            matched_label=label,
        )

    is_paynow = _is_paynow_like(desc_upper)
    return Categorization(
        category="Paynow" if is_paynow else "Others",
        subcategory="PayNow" if is_paynow else "Unparsable",
        contact_id=None,
        is_excluded=False,
        exclusion_reason=None,
        needs_review=is_paynow,
        matched_label=_paynow_label(raw_description, amount) if is_paynow else None,
    )
