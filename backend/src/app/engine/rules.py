"""Priority-ordered categorization rules engine per docs/technical-spec.md §4.

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

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from app.engine import paynow
from app.engine.card_payments import looks_like_card_bill_payment, looks_like_payment_received_on_card

CARD_PAYMENT_EXCLUSION_REASON = (
    "Credit card bill payment - the actual spending is already counted on the card's own statement"
)
CARD_PAYMENT_RECEIVED_EXCLUSION_REASON = (
    "Payment settling this card's balance - money moved between your own accounts, not income"
)


@dataclass
class CategorizationRequest:
    """The per-row half of categorize()'s input - built fresh for each
    transaction being categorized. posting_account_is_card lives here
    (rather than on CategorizationRuleset) because it depends on which
    account this specific transaction posted to, not on the pass as a
    whole - a single upload can mix rows from both a bank and a card
    account."""

    raw_description: str
    amount: float = 0.0
    posting_account_is_card: bool = False


@dataclass
class CategorizationRuleset:
    """The per-pass half of categorize()'s input - built once per upload,
    recategorize, or rule-rerun pass and reused unchanged across every row
    in that pass, since none of these fields depend on the row being
    categorized."""

    rules: Sequence[Mapping[str, Any]]
    contact_identifiers: Sequence[Mapping[str, Any]]
    category_directions: Mapping[str, str] = field(default_factory=dict)
    has_card_account: bool = False


@dataclass
class Categorization:
    category: str
    subcategory: str | None
    contact_id: int | None
    is_excluded: bool
    exclusion_reason: str | None
    needs_review: bool
    matched_label: str | None
    # Whether raw_description itself carries a PayNow scheme marker
    # (engine/paynow.py::is_paynow_transfer), independent of how the
    # transaction was actually resolved (rule/contact/fallback) - computed
    # once here so callers that need it (e.g. gating "save as contact" vs.
    # "save as rule" in the review dialogs) don't have to recompute it.
    is_paynow: bool


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


def categorize(request: CategorizationRequest, ruleset: CategorizationRuleset) -> Categorization:
    """request carries the per-row inputs (description, amount, and which
    kind of account it posted to); ruleset carries the per-pass inputs
    (rules, contacts, category directions, and whether any card account is
    known) that stay the same across every row in one upload/recategorize/
    rerun pass - see CategorizationRequest/CategorizationRuleset above.

    has_card_account: True if any credit card account is known - already
    committed, or parsed in the same upload batch. posting_account_is_card:
    True if the transaction being categorized itself lives on a card
    account (never auto-excluded as a "pay my card bill" transfer - a card
    can't pay itself). amount: signed transaction amount - drives both the
    inflow/outflow direction check against category_directions and the
    "PayNow from/to" label wording."""
    raw_description = request.raw_description
    amount = request.amount
    posting_account_is_card = request.posting_account_is_card
    rules = ruleset.rules
    contact_identifiers = ruleset.contact_identifiers
    category_directions = ruleset.category_directions
    has_card_account = ruleset.has_card_account

    desc_upper = raw_description.upper()
    direction = _direction_of(amount)
    is_paynow = paynow.is_paynow_transfer(desc_upper)

    for rule in rules:  # must already be sorted by priority ASC
        if rule["match_pattern"].upper() in desc_upper:
            if rule["is_exclusion_rule"]:
                if rule["direction"] != direction:
                    continue  # this exclusion rule was scoped to the other direction - keep looking
                return Categorization(
                    category=_fallback_category(direction),
                    subcategory=None,
                    contact_id=None,
                    is_excluded=True,
                    exclusion_reason=rule["exclusion_reason"],
                    needs_review=False,
                    matched_label=None,
                    is_paynow=is_paynow,
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
                is_paynow=is_paynow,
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
            is_paynow=is_paynow,
        )

    if direction == "inflow" and posting_account_is_card and looks_like_payment_received_on_card(desc_upper):
        # The mirror of the check above, on the other side of the same
        # payment. This one needs no has_card_account gate: the transaction
        # is posting to a card account, so a payment credit there is by
        # definition settling that card - there's no reading under which it
        # is income, whether or not the paying account was ever uploaded.
        return Categorization(
            category=_fallback_category(direction),
            subcategory=None,
            contact_id=None,
            is_excluded=True,
            exclusion_reason=CARD_PAYMENT_RECEIVED_EXCLUSION_REASON,
            needs_review=False,
            matched_label="Credit Card Payment",
            is_paynow=is_paynow,
        )

    contact = find_matching_contact(raw_description, contact_identifiers)
    if contact is not None:
        # A contact's default category is stored per-direction (someone who's
        # both paid and paid by the same PayNow identifier - a housemate
        # splitting bills, a client who's also a supplier - needs both set
        # independently), so this reads straight off whichever column matches
        # the transaction's own direction rather than the old single-column
        # "redirect Paynow<->Paynow Received and hope" approach.
        column = "default_category_outflow" if direction == "outflow" else "default_category_inflow"
        stored_category = contact[column]
        if stored_category and _category_direction(category_directions, stored_category) == direction:
            name = contact["name"] if "name" in contact.keys() else None
            label = (
                paynow.contact_label(name, amount) if paynow.is_paynow_category(stored_category) and name else name
            )
            return Categorization(
                category=stored_category,
                subcategory=contact["default_subcategory"],
                contact_id=contact["contact_id"],
                is_excluded=False,
                exclusion_reason=None,
                needs_review=False,
                matched_label=label,
                is_paynow=is_paynow,
            )
        # else: this contact has no default set for this transaction's
        # direction (or, defensively, a direction-mismatched one) - fall
        # through to the generic PayNow-marker/fallback tier below instead
        # of forcing an absent or wrong category.

    category = paynow.category_for_direction(amount) if is_paynow else _fallback_category(direction)
    return Categorization(
        category=category,
        subcategory="PayNow" if is_paynow else "Unparsable",
        contact_id=None,
        is_excluded=False,
        exclusion_reason=None,
        needs_review=is_paynow,
        matched_label=paynow.label(raw_description, amount) if is_paynow else None,
        is_paynow=is_paynow,
    )
