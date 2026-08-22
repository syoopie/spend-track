from app import rule_catalog
from app.db import _connect, init_db


def make_conn(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return _connect(db_path)


def test_fetch_active_rules_orders_by_priority_ascending(tmp_path):
    conn = make_conn(tmp_path)
    rule_catalog.insert_rule(
        conn, priority=50, match_pattern="ZZZ", target_category="Others", direction="outflow"
    )
    rule_catalog.insert_rule(
        conn, priority=10, match_pattern="AAA", target_category="Others", direction="outflow"
    )
    conn.commit()

    rules = rule_catalog.fetch_active_rules(conn)
    user_rules = [r for r in rules if not r["is_default"]]
    assert [r["match_pattern"] for r in user_rules] == ["AAA", "ZZZ"]


def test_next_user_rule_priority_is_one_past_the_current_max(tmp_path):
    conn = make_conn(tmp_path)
    assert rule_catalog.next_user_rule_priority(conn) == 1

    rule_catalog.insert_rule(conn, priority=1, match_pattern="A", target_category="Others", direction="outflow")
    rule_catalog.insert_rule(conn, priority=5, match_pattern="B", target_category="Others", direction="outflow")
    conn.commit()

    assert rule_catalog.next_user_rule_priority(conn) == 6


def test_category_direction_returns_the_live_category_direction(tmp_path):
    conn = make_conn(tmp_path)
    assert rule_catalog.category_direction(conn, "Salary") == "inflow"
    assert rule_catalog.category_direction(conn, "Transport") == "outflow"


def test_category_direction_falls_back_to_default_for_unknown_category(tmp_path):
    conn = make_conn(tmp_path)
    assert rule_catalog.category_direction(conn, "Not A Real Category") == "outflow"
    assert rule_catalog.category_direction(conn, "Not A Real Category", default="inflow") == "inflow"


def test_category_direction_returns_default_for_none_category(tmp_path):
    conn = make_conn(tmp_path)
    assert rule_catalog.category_direction(conn, None) == "outflow"
    assert rule_catalog.category_direction(conn, None, default="inflow") == "inflow"


def test_insert_rule_persists_all_fields(tmp_path):
    conn = make_conn(tmp_path)
    rule_id = rule_catalog.insert_rule(
        conn,
        priority=3,
        match_pattern="GRAB",
        target_category="Transport",
        target_subcategory="Rideshare",
        is_exclusion_rule=False,
        exclusion_reason=None,
        direction="outflow",
    )
    conn.commit()

    row = conn.execute("SELECT * FROM rules WHERE id = ?", (rule_id,)).fetchone()
    assert row["match_pattern"] == "GRAB"
    assert row["target_category"] == "Transport"
    assert row["target_subcategory"] == "Rideshare"
    assert row["direction"] == "outflow"
    assert not row["is_exclusion_rule"]


def test_insert_rule_supports_exclusion_rules(tmp_path):
    conn = make_conn(tmp_path)
    rule_id = rule_catalog.insert_rule(
        conn,
        priority=1,
        match_pattern="INTERNAL TRANSFER",
        target_category="Others",
        is_exclusion_rule=True,
        exclusion_reason="Self-transfer",
        direction="outflow",
    )
    conn.commit()

    row = conn.execute("SELECT * FROM rules WHERE id = ?", (rule_id,)).fetchone()
    assert row["is_exclusion_rule"]
    assert row["exclusion_reason"] == "Self-transfer"
