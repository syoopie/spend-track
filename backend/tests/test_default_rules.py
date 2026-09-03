import pytest

from app.engine.default_rules import DEFAULT_PAYNOW_RULE_BANK, DEFAULT_RULE_BANK, iter_default_rules
from app.engine.pattern_match import pattern_matches


def test_paynow_tier_is_sorted_after_every_other_default_rule():
    flat = iter_default_rules()
    bank_pattern_count = sum(len(entries) for entries in DEFAULT_RULE_BANK.values())
    paynow_patterns = {p for p, _cat, _label in DEFAULT_PAYNOW_RULE_BANK}
    for i, (pattern, _category, _label) in enumerate(flat):
        if pattern in paynow_patterns:
            assert i >= bank_pattern_count


def test_investing_paynow_rule_present_and_targets_investing_category():
    matches = [(p, c, l) for p, c, l in iter_default_rules() if p == "INTERACTIVE BR SG"]
    assert matches == [("INTERACTIVE BR SG", "Investing", "Interactive Brokers")]


def test_insurance_and_tax_rules_target_bills_and_fees():
    flat = {p: c for p, c, _l in iter_default_rules()}
    assert flat["IRAS"] == "Bills & Fees"
    assert flat["INCOME INSURANCE"] == "Bills & Fees"


def test_default_rule_bank_never_targets_others_or_paynow_transfers():
    for _pattern, category, _label in iter_default_rules():
        assert category not in ("Others", "Paynow")


def test_reconcile_default_rules_picks_up_new_patterns_without_wiping_dbs(tmp_path, monkeypatch):
    """_reconcile_default_rules must run every startup (not just once) so a
    newly-added default-rules.py entry reaches an already-initialized DB."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("SG_TRACKER_DB_PATH", str(db_path))
    from app import db as db_module

    db_module.init_db(db_path)
    with db_module.get_conn() as conn:
        before = conn.execute("SELECT COUNT(*) FROM rules WHERE is_default = 1").fetchone()[0]
    assert before > 50

    # Re-running init_db() (as happens on every app startup) must not create
    # duplicates and must still reflect the current default_rules.py content.
    db_module.init_db(db_path)
    with db_module.get_conn() as conn:
        after = conn.execute("SELECT COUNT(*) FROM rules WHERE is_default = 1").fetchone()[0]
        pattern = conn.execute(
            "SELECT match_pattern FROM rules WHERE is_default = 1 AND match_pattern = 'IRAS'"
        ).fetchone()
    assert after == before
    assert pattern is not None


# The short acronym/brand patterns are the ones worth pinning against false
# positives: Golden Village only ever prints as "GV <venue>", Cheers as
# "CHEERS - <place>". engine/pattern_match.py matches any pattern of six
# characters or fewer on alphanumeric word boundaries, so none of them can
# fire inside a longer word; iter_default_rules' longest-first sort still
# means they only get a turn after every more specific pattern has missed.
SHORT_PATTERN_CASES = [
    ("Misc DR-Debit Card 13 MAY 1634 0236145 GV PLAZA SINGAPURA SINGAPORE SG", "Entertainment"),
    ("Misc DR-Debit Card 04 FEB 1634 0231251 GV BUGIS+ SINGAPORE SG", "Entertainment"),
    ("Misc DR-Debit Card 07 JUN 1634 2213593 CHEERS - COLLEGE AVE WESTSINGAPORE SG", "Groceries"),
    ("Misc DR-Debit Card 05 MAY 1634 4883085 7-ELEVEN - DUO GALLERIA Singapore SG", "Groceries"),
]

SHORT_PATTERN_NON_MATCHES = [
    "GIRO PAYMENT CHEERSFUL HOLDINGS PTE LTD",
    "NETS Debit-Consumer LOGVIEW SYSTEMS 12345678",
]

# Real lines where a short pattern used to fire inside a longer word and put
# the transaction in the wrong category. (description, category-it-must-not-be)
SHORT_PATTERN_MISFIRES = [
    ("Misc DR-Debit Card 11 MAY 1634 4858123 VENUS BEAUTY EAS SINGAPORE SGP", "Education"),
    ("Misc DR-NETS 03 JUN 1634 0231251 NTUC FP HARBOURFRONT SINGAPORE SG", "Education"),
    ("Misc DR-Debit Card 09 JUN 1634 1122334 ESPRESSO BAR SINGAPORE SG", "Transport"),
    ("Misc DR-Debit Card 14 JUN 1634 5566778 STEAMBOAT CORNER SINGAPORE SG", "Entertainment"),
]


def _first_match(description: str) -> tuple[str, str, str] | None:
    upper = description.upper()
    for pattern, category, label in iter_default_rules():
        if pattern_matches(pattern, upper):
            return pattern, category, label
    return None


@pytest.mark.parametrize("description, expected_category", SHORT_PATTERN_CASES)
def test_short_merchant_patterns_match_the_lines_they_were_written_for(description, expected_category):
    match = _first_match(description)
    assert match is not None, description
    assert match[1] == expected_category


@pytest.mark.parametrize("description", SHORT_PATTERN_NON_MATCHES)
def test_short_merchant_patterns_do_not_fire_on_a_longer_word(description):
    """A short pattern is boundary-matched (engine/pattern_match.py), so
    "CHEERSFUL HOLDINGS" is not groceries and "LOGVIEW SYSTEMS" is not a
    cinema - no trailing-space hack needed."""
    match = _first_match(description)
    assert match is None or match[0].strip() not in ("CHEERS", "GV")


@pytest.mark.parametrize("description, wrong_category", SHORT_PATTERN_MISFIRES)
def test_short_patterns_no_longer_misfire_inside_a_longer_word(description, wrong_category):
    match = _first_match(description)
    assert match is None or match[1] != wrong_category


TRAVEL_CASES = [
    ("Misc DR-Debit Card 16 MAY 1634 6594052 AIRBNB * HMT8PKY8J8 653-163-1004 GB", "Airbnb"),
    ("Misc DR-Debit Card 20 MAY 1634 4062040 AGODA.COM NARITA TOB Internet SG", "Agoda"),
    ("Misc DR-Debit Card 02 JAN 1634 1111111 FLYSCOOT.COM SINGAPORE SG", "Scoot"),
    ("Misc DR-Debit Card 02 JAN 1634 1111112 SINGAPORE AIRLINES SINGAPORE SG", "Singapore Airlines"),
    ("Misc DR-Debit Card 02 JAN 1634 1111113 HILTON GARDEN INN TOKYO JP", "Hilton"),
]


@pytest.mark.parametrize("description, expected_label", TRAVEL_CASES)
def test_travel_merchants_categorize_as_travel(description, expected_label):
    match = _first_match(description)
    assert match is not None, description
    assert match[1] == "Travel"
    assert match[2] == expected_label


def test_scoot_cafe_is_food_not_travel():
    """A boarding-pass cafe purchase is food. It stays Food & Drink because
    "SCOOT CAFE" is longer than any travel pattern and iter_default_rules
    sorts longest-first - and there is no bare "SCOOT" rule to fight it,
    since SCOOT is a substring of SCOOTER."""
    match = _first_match("Misc DR-Debit Card 27 MAY 1634 1023636 SCOOT CAFE_SATS APS SINGAPORE SG")
    assert match is not None
    assert match[1] == "Food & Drink"


def test_no_travel_pattern_fires_on_a_scooter_or_a_hibiscus():
    for description in ("GRAB SCOOTER RENTAL SINGAPORE", "HIBISCUS FLORIST SINGAPORE SG"):
        match = _first_match(description)
        assert match is None or match[1] != "Travel", description
