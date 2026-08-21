"""Priority-ordered categorization rules engine per TECHNICAL_SPEC.md §4.

Rules are evaluated in priority ASC order (priority 1 = highest precedence,
evaluated first); the first matching rule wins - this includes both
user-created rules and the seeded, immutable `is_default` word-bank rules,
which are given a priority far below any user rule so user rules always win
on the same description (see migrations.py::reconcile_default_rules). If no
rule matches, fall back to a contact-identifier match, then to a PayNow
check (engine/paynow.py), then to 'Others'/'Other Income'.

Every category is locked to one direction ('inflow' or 'outflow' - see
migrations.py's DEFAULT_CATEGORIES and schema.sql's categories.direction).
A rule or contact whose target category doesn't match the transaction's
actual amount sign is skipped rather than applied - this is what stops,
say, a refund landing under an outflow-shaped category like "Transport"
just because its description happens to contain a transport merchant's
name. category_directions must reflect the live `categories` table
(see repo.py::fetch_category_directions); an unknown category name is
treated as outflow, matching the column's own DB default.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.engine import paynow
from app.engine.card_payments import looks_like_card_bill_payment

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


def _direction_of(amount: float) -> str:
    return "inflow" if amount > 0 else "outflow"


def _category_direction(category_directions: Mapping[str, str], category: str) -> str:
    # The two PayNow categories' direction is authoritative from
    # engine/paynow.py itself, not the caller-supplied map - a caller that
    # forgets (or a test that doesn't bother) to pass a full categories
    # snapshot shouldn't be able to make a real PayNow match distrust itself
    # and fall through, losing the contact name in the label.
    if paynow.is_paynow_category(category):
        return "inflow" if category == paynow.CATEGORY_RECEIVED else "outflow"
    return category_directions.get(category, "outflow")


def _fallback_category(direction: str) -> str:
    return "Other Income" if direction == "inflow" else "Others"


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
    category_directions: Mapping[str, str] = {},
    has_card_account: bool = False,
    posting_account_is_card: bool = False,
) -> Categorization:
    """has_card_account: True if any credit card account is known - already
    committed, or parsed in the same upload batch. posting_account_is_card:
    True if the transaction being categorized itself lives on a card
    account (never auto-excluded as a "pay my card bill" transfer - a card
    can't pay itself). amount: signed transaction amount - drives both the
    inflow/outflow direction check against category_directions and the
    "PayNow from/to" label wording."""
    desc_upper = raw_description.upper()
    direction = _direction_of(amount)

    for rule in rules:  # must already be sorted by priority ASC
        if rule["match_pattern"].upper() in desc_upper:
            if rule["is_exclusion_rule"]:
                return Categorization(
                    category=_fallback_category(direction),
                    subcategory=None,
                    contact_id=None,
                    is_excluded=True,
                    exclusion_reason=rule["exclusion_reason"],
                    needs_review=False,
                    matched_label=None,
                )
            category = rule["target_category"]
            if _category_direction(category_directions, category) != direction:
                continue  # wrong-direction match on this rule - keep looking, don't stop here
            display_label = rule["display_label"] if "display_label" in rule.keys() else None
            label = paynow.label(raw_description, amount) if paynow.is_paynow_category(category) else (
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

    if (
        direction == "outflow"
        and has_card_account
        and not posting_account_is_card
        and looks_like_card_bill_payment(desc_upper)
    ):
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
        stored_category = contact["default_category"]
        category = paynow.redirect_for_direction(stored_category, amount)
        if _category_direction(category_directions, category) == direction:
            name = contact["name"] if "name" in contact.keys() else None
            label = paynow.contact_label(name, amount) if paynow.is_paynow_category(category) and name else name
            return Categorization(
                category=category,
                subcategory=contact["default_subcategory"],
                contact_id=contact["contact_id"],
                is_excluded=False,
                exclusion_reason=None,
                needs_review=False,
                matched_label=label,
            )
        # else: this contact's category doesn't fit the transaction's actual
        # direction and isn't a Paynow<->Paynow Received case either - fall
        # through to the generic PayNow-marker/fallback tier below instead
        # of forcing a mismatched category.

    is_paynow = paynow.is_paynow_transfer(desc_upper)
    category = paynow.category_for_direction(amount) if is_paynow else _fallback_category(direction)
    return Categorization(
        category=category,
        subcategory="PayNow" if is_paynow else "Unparsable",
        contact_id=None,
        is_excluded=False,
        exclusion_reason=None,
        needs_review=is_paynow,
        matched_label=paynow.label(raw_description, amount) if is_paynow else None,
    )
