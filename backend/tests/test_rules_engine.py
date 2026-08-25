from app.engine.rules import Categorization, CategorizationRequest, CategorizationRuleset, categorize


def cat(
    raw_description,
    rules=(),
    contacts=(),
    *,
    amount=0.0,
    category_directions=None,
    has_card_account=False,
    posting_account_is_card=False,
) -> Categorization:
    """Test-local builder for categorize()'s two-part input - mirrors how a
    real caller builds one CategorizationRuleset per pass and one
    CategorizationRequest per row (see routers/statements.py,
    routers/transactions.py, engine/rule_rerun.py)."""
    request = CategorizationRequest(
        raw_description=raw_description, amount=amount, posting_account_is_card=posting_account_is_card
    )
    ruleset = CategorizationRuleset(
        rules=rules,
        contact_identifiers=contacts,
        category_directions=category_directions or {},
        has_card_account=has_card_account,
    )
    return categorize(request, ruleset)


def rule(
    priority,
    pattern,
    category=None,
    subcategory=None,
    is_exclusion=False,
    reason=None,
    display_label=None,
    direction="outflow",
):
    return {
        "priority": priority,
        "match_pattern": pattern,
        "target_category": category,
        "target_subcategory": subcategory,
        "is_exclusion_rule": is_exclusion,
        "exclusion_reason": reason,
        "display_label": display_label,
        "direction": direction,
    }


def test_first_matching_rule_wins_by_priority_order():
    rules = [
        rule(1, "SP GROUP", "Bills & Fees"),
        rule(2, "GRAB", "Transport"),
    ]
    result = cat("SP GROUP UTILITIES", rules, [])
    assert result.category == "Bills & Fees"
    assert not result.is_excluded


def test_matched_label_falls_back_to_title_cased_pattern():
    rules = [rule(1, "SHENG SIONG", "Groceries")]
    result = cat("SHENG SIONG 1 STATION MKT SINGAPORE", rules, [])
    assert result.matched_label == "Sheng Siong"


def test_matched_label_uses_rule_display_label_when_set():
    rules = [rule(1, "BUS/MRT", "Transport", display_label="Public Transport")]
    result = cat("BUS/MRT 865044496 SINGAPORE", rules, [])
    assert result.matched_label == "Public Transport"


def test_exclusion_rule_sets_excluded_and_reason():
    rules = [rule(1, "INTERNAL TRANSFER", is_exclusion=True, reason="Self-transfer between own accounts")]
    result = cat("INTERNAL TRANSFER - SAVINGS", rules, [])
    assert result.is_excluded
    assert result.exclusion_reason == "Self-transfer between own accounts"


def test_self_transfer_between_own_uob_accounts_real_world_case():
    """From the real UOB samples: 'Bill Payment mBK-UOB Cards 4265884081509100'
    is the account statement's outflow for paying one's own UOB credit card -
    exactly the exclusion-rule scenario the UX calls out."""
    rules = [rule(1, "MBK-UOB CARDS", is_exclusion=True, reason="Self-transfer to own UOB card")]
    result = cat("Bill Payment mBK-UOB Cards 4265884081509100", rules, [])
    assert result.is_excluded
    assert result.exclusion_reason == "Self-transfer to own UOB card"


def test_exclusion_rule_does_not_apply_to_the_opposite_direction():
    """A real gap this closes: exclusion rules used to match regardless of
    direction, so a self-transfer pattern also present on the inflow leg of
    the same transfer (or any other coincidental match) would silently get
    excluded from totals too, even for a rule the user only meant for one
    direction."""
    rules = [rule(1, "INTERNAL TRANSFER", is_exclusion=True, reason="Self-transfer", direction="outflow")]
    result = cat("INTERNAL TRANSFER - SAVINGS", rules, [], amount=50.00)  # inflow
    assert not result.is_excluded


def test_exclusion_rule_applies_to_its_own_direction():
    rules = [rule(1, "INTERNAL TRANSFER", is_exclusion=True, reason="Self-transfer", direction="inflow")]
    result = cat("INTERNAL TRANSFER - SAVINGS", rules, [], amount=50.00)  # inflow
    assert result.is_excluded


def test_no_rule_match_falls_back_to_contact():
    contacts = [
        {
            "contact_id": 7,
            "name": "Auntie Mei",
            "identifier": "+65 9123 4567",
            "default_category_outflow": "Paynow",
            "default_category_inflow": None,
            "default_subcategory": None,
        }
    ]
    result = cat("PAYNOW-FAST PAYNOW OTHR +65 9123 4567", [], contacts, amount=-25.00)
    assert result.category == "Paynow"
    assert result.contact_id == 7
    assert result.matched_label == "PayNow to Auntie Mei"


def test_contact_match_paynow_label_says_from_for_incoming_amount():
    """The inflow half needs its own explicit default (unlike the old
    single-column model, an outflow default no longer auto-bridges to the
    inflow PayNow category - see test_contact_with_only_outflow_default_
    does_not_resolve_inflow_transactions below)."""
    contacts = [
        {
            "contact_id": 7,
            "name": "Auntie Mei",
            "identifier": "+65 9123 4567",
            "default_category_outflow": "Paynow",
            "default_category_inflow": "Paynow Received",
            "default_subcategory": None,
        }
    ]
    result = cat("PAYNOW-FAST PAYNOW OTHR +65 9123 4567", [], contacts, amount=25.00)
    assert result.matched_label == "PayNow from Auntie Mei"
    assert result.contact_id == 7


def test_no_rule_or_contact_match_flags_paynow_for_review_in_its_own_category():
    result = cat("PAYNOW-FAST PIB2605050213183371 UNKNOWN PERSON", [], [], amount=-25.00)
    assert result.category == "Paynow"
    assert result.subcategory == "PayNow"
    assert result.needs_review is True
    assert result.matched_label == "PayNow to UNKNOWN PERSON"


def test_paynow_fallback_label_keeps_phone_number_when_no_name_present():
    result = cat("PAYNOW-FAST PAYNOW OTHR +65 9123 4567", [], [], amount=-25.00)
    assert result.matched_label == "PayNow to +65 9123 4567"


def test_paynow_fallback_label_says_from_for_incoming_amount():
    result = cat("PAYNOW-FAST PAYNOW OTHR +65 9123 4567", [], [], amount=25.00)
    assert result.matched_label == "PayNow from +65 9123 4567"


def test_non_paynow_unmatched_defaults_to_others_unparsable_without_review_flag():
    result = cat("SOME RANDOM MERCHANT XYZ", [], [])
    assert result.category == "Others"
    assert result.subcategory == "Unparsable"
    assert result.needs_review is False


def test_rules_take_priority_over_contact_match():
    rules = [rule(1, "GRAB", "Transport")]
    contacts = [
        {
            "contact_id": 1,
            "identifier": "GRAB",
            "default_category_outflow": "Others",
            "default_category_inflow": None,
            "default_subcategory": None,
        }
    ]
    result = cat("GRAB Ride", rules, contacts)
    assert result.category == "Transport"
    assert result.contact_id is None


# --- credit card bill payment double-counting (has_card_account) -----------


def test_card_bill_payment_excluded_when_a_card_account_exists():
    """Real UOB account statement text for GIRO-paying one's own UOB card."""
    result = cat(
        "Bill Payment mBK-UOB Cards 4265884081509100",
        [],
        [],
        has_card_account=True,
        posting_account_is_card=False,
    )
    assert result.is_excluded
    assert "already counted" in result.exclusion_reason


def test_card_bill_payment_not_excluded_without_a_known_card_account():
    """No card statement uploaded (has_card_account=False, the default) -
    the payment is the only record of this money leaving, so it must not
    be silently hidden from totals."""
    result = cat("Bill Payment mBK-UOB Cards 4265884081509100", [], [])
    assert not result.is_excluded
    assert result.category == "Others"


def test_card_bill_payment_heuristic_never_applies_to_a_card_account_itself():
    result = cat(
        "Bill Payment mBK-UOB Cards 4265884081509100",
        [],
        [],
        has_card_account=True,
        posting_account_is_card=True,
    )
    assert not result.is_excluded


def test_explicit_rule_overrides_card_bill_payment_heuristic():
    rules = [rule(1, "UOB CARDS", "Bills & Fees", display_label="UOB Card Bill")]
    result = cat(
        "Bill Payment mBK-UOB Cards 4265884081509100",
        rules,
        [],
        has_card_account=True,
        posting_account_is_card=False,
    )
    assert not result.is_excluded
    assert result.category == "Bills & Fees"
    assert result.matched_label == "UOB Card Bill"


def test_payment_credit_on_a_card_statement_is_excluded():
    """The other half of the same bill payment. Without this the card's own
    "PAYMT THRU..." credit counts as inflow, so a year of statements reports
    every bill payment as income."""
    result = cat(
        "PAYMT THRU E-BANK/HOMEB/CYBERB",
        [],
        [],
        amount=150.00,
        posting_account_is_card=True,
    )
    assert result.is_excluded
    assert "not income" in result.exclusion_reason
    assert result.matched_label == "Credit Card Payment"


def test_payment_credit_exclusion_needs_no_known_bank_account():
    """Unlike the outflow half, this one isn't gated on having seen the
    paying account: a payment credit posting to a card is settling that
    card either way, and is never income."""
    result = cat(
        "PAYMENT - THANK YOU",
        [],
        [],
        amount=200.00,
        has_card_account=False,
        posting_account_is_card=True,
    )
    assert result.is_excluded


def test_payment_credit_exclusion_only_applies_on_a_card_account():
    """The same words arriving in a bank account are someone paying *you*."""
    result = cat("PAYMENT RECEIVED", [], [], amount=200.00, posting_account_is_card=False)
    assert not result.is_excluded


def test_payment_credit_exclusion_never_fires_for_an_outflow_on_a_card():
    result = cat("PAYMT THRU E-BANK/HOMEB/CYBERB", [], [], amount=-150.00, posting_account_is_card=True)
    assert not result.is_excluded


def test_a_refund_credit_on_a_card_is_not_treated_as_a_bill_payment():
    """Card statements carry real credits too - a refund is money coming
    back, and must keep its own category rather than vanishing from totals."""
    rules = [rule(1, "REFUND", "Refunds & Reimbursements", direction="inflow")]
    result = cat(
        "SAMPLE ONLINE STORE REFUND",
        rules,
        [],
        amount=49.90,
        category_directions={"Refunds & Reimbursements": "inflow"},
        posting_account_is_card=True,
    )
    assert not result.is_excluded
    assert result.category == "Refunds & Reimbursements"


def test_explicit_rule_overrides_the_payment_credit_exclusion():
    rules = [rule(1, "PAYMT THRU", "Other Income", display_label="Card Payment In", direction="inflow")]
    result = cat(
        "PAYMT THRU E-BANK/HOMEB/CYBERB",
        rules,
        [],
        amount=150.00,
        category_directions={"Other Income": "inflow"},
        posting_account_is_card=True,
    )
    assert not result.is_excluded
    assert result.category == "Other Income"


def test_card_bill_payment_heuristic_never_fires_for_inflow():
    """The heuristic is conceptually outflow-only (paying your own bill is
    money leaving), so the direction check is explicit rather than assumed
    from the description alone."""
    result = cat(
        "Bill Payment mBK-UOB Cards 4265884081509100",
        [],
        [],
        amount=150.00,
        has_card_account=True,
        posting_account_is_card=False,
    )
    assert not result.is_excluded


# --- direction-locked categories (inflow vs outflow) ------------------------

DIRECTIONS = {
    "Transport": "outflow",
    "Refunds & Reimbursements": "inflow",
    "Investment Income": "inflow",
    "Salary": "inflow",
}


def test_outflow_rule_is_skipped_for_an_inflow_transaction():
    """The exact bug report this feature exists to fix: a credit card
    refund for a prior Grab ride shares "GRAB" in its description with real
    Grab spending, but the refund is money in - it must not land under the
    outflow-only "Transport" category just because the text matches."""
    rules = [rule(1, "GRAB", "Transport")]
    result = cat("GRAB REFUND SINGAPORE", rules, [], amount=12.50, category_directions=DIRECTIONS)
    assert result.category != "Transport"


def test_inflow_transaction_falls_through_a_wrong_direction_rule_to_the_next_match():
    rules = [
        rule(1, "GRAB", "Transport"),  # wrong direction - must be skipped, not just stop the whole match
        rule(2, "REFUND", "Refunds & Reimbursements"),
    ]
    result = cat("GRAB REFUND SINGAPORE", rules, [], amount=12.50, category_directions=DIRECTIONS)
    assert result.category == "Refunds & Reimbursements"


def test_inflow_with_no_matching_rule_falls_back_to_other_income_not_others():
    result = cat("SOME RANDOM CREDIT XYZ", [], [], amount=12.50, category_directions=DIRECTIONS)
    assert result.category == "Other Income"
    assert result.subcategory == "Unparsable"


def test_outflow_unmatched_still_falls_back_to_others():
    result = cat("SOME RANDOM MERCHANT XYZ", [], [], amount=-12.50, category_directions=DIRECTIONS)
    assert result.category == "Others"


def test_contact_category_direction_mismatch_falls_through_instead_of_forcing_it():
    """Defensive case: a contact's inflow default somehow holds an
    outflow-only category name (bad data, e.g. a direct DB edit - the UI
    itself only ever offers direction-filtered category pickers). An inflow
    transaction identified as being from that contact must not be
    force-categorized under an outflow-only bucket."""
    contacts = [
        {
            "contact_id": 3,
            "name": "Some Vendor",
            "identifier": "VENDOR123",
            "default_category_outflow": None,
            "default_category_inflow": "Transport",
            "default_subcategory": None,
        }
    ]
    result = cat("VENDOR123 CREDIT", [], contacts, amount=50.00, category_directions=DIRECTIONS)
    assert result.category != "Transport"
    assert result.contact_id is None  # the mismatched contact match wasn't used at all


def test_contact_with_only_outflow_default_does_not_resolve_inflow_transactions():
    """Unlike the old single-column model (which redirected Paynow <->
    Paynow Received live based on the transaction's own amount), a contact
    with no inflow default set gets no special treatment on an inflow
    transaction - it falls all the way through to the generic PayNow-marker
    fallback, unattributed to this contact."""
    contacts = [
        {
            "contact_id": 7,
            "name": "Auntie Mei",
            "identifier": "+65 9123 4567",
            "default_category_outflow": "Paynow",
            "default_category_inflow": None,
            "default_subcategory": None,
        }
    ]
    result = cat(
        "PAYNOW-FAST PAYNOW OTHR +65 9123 4567", [], contacts, amount=25.00, category_directions=DIRECTIONS
    )
    assert result.category == "Paynow Received"  # still a PayNow marker match, just not via the contact
    assert result.contact_id is None


def test_contact_with_explicit_inflow_default_resolves_inflow_transactions():
    contacts = [
        {
            "contact_id": 7,
            "name": "Auntie Mei",
            "identifier": "+65 9123 4567",
            "default_category_outflow": "Paynow",
            "default_category_inflow": "Paynow Received",
            "default_subcategory": None,
        }
    ]
    result = cat(
        "PAYNOW-FAST PAYNOW OTHR +65 9123 4567", [], contacts, amount=25.00, category_directions=DIRECTIONS
    )
    assert result.category == "Paynow Received"
    assert result.contact_id == 7


def test_one_ruleset_is_safely_reused_across_many_requests():
    """The intended real-world usage (see routers/statements.py,
    routers/transactions.py, engine/rule_rerun.py): one CategorizationRuleset
    is built once per upload/recategorize/rerun pass and passed unchanged to
    categorize() for every row in that pass. Two different requests against
    the same ruleset instance must not leak state into each other."""
    rules = [rule(1, "GRAB", "Transport")]
    ruleset = CategorizationRuleset(rules=rules, contact_identifiers=[], category_directions=DIRECTIONS)

    grab_result = categorize(CategorizationRequest(raw_description="GRAB Ride"), ruleset)
    other_result = categorize(CategorizationRequest(raw_description="SOME RANDOM MERCHANT XYZ"), ruleset)

    assert grab_result.category == "Transport"
    assert other_result.category == "Others"
