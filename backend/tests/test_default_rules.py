from app.engine.default_rules import DEFAULT_PAYNOW_RULE_BANK, DEFAULT_RULE_BANK, iter_default_rules


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
        assert category not in ("Others", "PayNow Transfers")


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
