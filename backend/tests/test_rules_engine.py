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
            "default_category": "PayNow Transfers",
            "default_subcategory": None,
        }
    ]
    result = categorize("PAYNOW-FAST PAYNOW OTHR +65 9123 4567", [], contacts)
    assert result.category == "PayNow Transfers"
    assert result.contact_id == 7
    assert result.matched_label == "PayNow to Auntie Mei"


def test_no_rule_or_contact_match_flags_paynow_for_review_in_its_own_category():
    result = categorize("PAYNOW-FAST PIB2605050213183371 UNKNOWN PERSON", [], [])
    assert result.category == "PayNow Transfers"
    assert result.subcategory == "PayNow"
    assert result.needs_review is True
    assert result.matched_label == "PayNow to UNKNOWN PERSON"


def test_paynow_fallback_label_keeps_phone_number_when_no_name_present():
    result = categorize("PAYNOW-FAST PAYNOW OTHR +65 9123 4567", [], [])
    assert result.matched_label == "PayNow to +65 9123 4567"


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
