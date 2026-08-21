from app.engine.rules import categorize


def rule(priority, pattern, category=None, subcategory=None, is_exclusion=False, reason=None, display_label=None):
    return {
        "priority": priority,
        "match_pattern": pattern,
        "target_category": category,
        "target_subcategory": subcategory,
        "is_exclusion_rule": is_exclusion,
        "exclusion_reason": reason,
        "display_label": display_label,
    }


def test_first_matching_rule_wins_by_priority_order():
    rules = [
        rule(1, "SP GROUP", "Bills & Fees"),
        rule(2, "GRAB", "Transport"),
    ]
    result = categorize("SP GROUP UTILITIES", rules, [])
    assert result.category == "Bills & Fees"
    assert not result.is_excluded


def test_matched_label_falls_back_to_title_cased_pattern():
    rules = [rule(1, "SHENG SIONG", "Groceries")]
    result = categorize("SHENG SIONG 1 STATION MKT SINGAPORE", rules, [])
    assert result.matched_label == "Sheng Siong"


def test_matched_label_uses_rule_display_label_when_set():
    rules = [rule(1, "BUS/MRT", "Transport", display_label="Public Transport")]
    result = categorize("BUS/MRT 865044496 SINGAPORE", rules, [])
    assert result.matched_label == "Public Transport"


def test_exclusion_rule_sets_excluded_and_reason():
    rules = [rule(1, "INTERNAL TRANSFER", is_exclusion=True, reason="Self-transfer between own accounts")]
    result = categorize("INTERNAL TRANSFER - SAVINGS", rules, [])
    assert result.is_excluded
    assert result.exclusion_reason == "Self-transfer between own accounts"


def test_self_transfer_between_own_uob_accounts_real_world_case():
    """From the real UOB samples: 'Bill Payment mBK-UOB Cards 4265884081509100'
    is the account statement's outflow for paying one's own UOB credit card -
    exactly the exclusion-rule scenario the UX calls out."""
    rules = [rule(1, "MBK-UOB CARDS", is_exclusion=True, reason="Self-transfer to own UOB card")]
    result = categorize("Bill Payment mBK-UOB Cards 4265884081509100", rules, [])
    assert result.is_excluded
    assert result.exclusion_reason == "Self-transfer to own UOB card"


def test_no_rule_match_falls_back_to_contact():
    contacts = [
        {
            "contact_id": 7,
            "name": "Auntie Mei",
            "identifier": "+65 9123 4567",
            "default_category": "Paynow",
            "default_subcategory": None,
        }
    ]
    result = categorize("PAYNOW-FAST PAYNOW OTHR +65 9123 4567", [], contacts, amount=-25.00)
    assert result.category == "Paynow"
    assert result.contact_id == 7
    assert result.matched_label == "PayNow to Auntie Mei"


def test_contact_match_paynow_label_says_from_for_incoming_amount():
    contacts = [
        {
            "contact_id": 7,
            "name": "Auntie Mei",
            "identifier": "+65 9123 4567",
            "default_category": "Paynow",
            "default_subcategory": None,
        }
    ]
    result = categorize("PAYNOW-FAST PAYNOW OTHR +65 9123 4567", [], contacts, amount=25.00)
    assert result.matched_label == "PayNow from Auntie Mei"


def test_no_rule_or_contact_match_flags_paynow_for_review_in_its_own_category():
    result = categorize("PAYNOW-FAST PIB2605050213183371 UNKNOWN PERSON", [], [], amount=-25.00)
    assert result.category == "Paynow"
    assert result.subcategory == "PayNow"
    assert result.needs_review is True
    assert result.matched_label == "PayNow to UNKNOWN PERSON"


def test_paynow_fallback_label_keeps_phone_number_when_no_name_present():
    result = categorize("PAYNOW-FAST PAYNOW OTHR +65 9123 4567", [], [], amount=-25.00)
    assert result.matched_label == "PayNow to +65 9123 4567"


def test_paynow_fallback_label_says_from_for_incoming_amount():
    result = categorize("PAYNOW-FAST PAYNOW OTHR +65 9123 4567", [], [], amount=25.00)
    assert result.matched_label == "PayNow from +65 9123 4567"


def test_non_paynow_unmatched_defaults_to_others_unparsable_without_review_flag():
    result = categorize("SOME RANDOM MERCHANT XYZ", [], [])
    assert result.category == "Others"
    assert result.subcategory == "Unparsable"
    assert result.needs_review is False


def test_rules_take_priority_over_contact_match():
    rules = [rule(1, "GRAB", "Transport")]
    contacts = [
        {
            "contact_id": 1,
            "identifier": "GRAB",
            "default_category": "Others",
            "default_subcategory": None,
        }
    ]
    result = categorize("GRAB Ride", rules, contacts)
    assert result.category == "Transport"
    assert result.contact_id is None


# --- credit card bill payment double-counting (has_card_account) -----------


def test_card_bill_payment_excluded_when_a_card_account_exists():
    """Real UOB account statement text for GIRO-paying one's own UOB card."""
    result = categorize(
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
    result = categorize("Bill Payment mBK-UOB Cards 4265884081509100", [], [])
    assert not result.is_excluded
    assert result.category == "Others"


def test_card_bill_payment_heuristic_never_applies_to_a_card_account_itself():
    result = categorize(
        "Bill Payment mBK-UOB Cards 4265884081509100",
        [],
        [],
        has_card_account=True,
        posting_account_is_card=True,
    )
    assert not result.is_excluded


def test_explicit_rule_overrides_card_bill_payment_heuristic():
    rules = [rule(1, "UOB CARDS", "Bills & Fees", display_label="UOB Card Bill")]
    result = categorize(
        "Bill Payment mBK-UOB Cards 4265884081509100",
        rules,
        [],
        has_card_account=True,
        posting_account_is_card=False,
    )
    assert not result.is_excluded
    assert result.category == "Bills & Fees"
    assert result.matched_label == "UOB Card Bill"
