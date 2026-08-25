from importlib import resources

from app.db import _connect, init_db


def _seed_transaction(conn, *, category, amount, fingerprint="fp1"):
    conn.execute(
        "INSERT INTO accounts (id, bank_name, account_number_masked, account_type) "
        "VALUES ('acc1', 'UOB', '1234', 'card') ON CONFLICT(id) DO NOTHING"
    )
    conn.execute(
        "INSERT INTO transactions (fingerprint, account_id, transaction_date, raw_description, amount, category) "
        "VALUES (?, 'acc1', '2026-01-01', 'GRAB REFUND SINGAPORE', ?, ?)",
        (fingerprint, amount, category),
    )
    conn.commit()


def test_stale_outflow_category_on_inflow_transaction_is_redirected_to_other_income(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)

    conn = _connect(db_path)
    _seed_transaction(conn, category="Transport", amount=12.50)
    conn.close()

    # Simulates the app restarting - re-running init_db is what a real
    # pre-direction-lock DB goes through on next launch.
    init_db(db_path)

    conn = _connect(db_path)
    row = conn.execute("SELECT category FROM transactions WHERE fingerprint = 'fp1'").fetchone()
    conn.close()
    assert row["category"] == "Other Income"


def test_stale_inflow_category_on_outflow_transaction_is_redirected_to_others(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)

    conn = _connect(db_path)
    _seed_transaction(conn, category="Salary", amount=-45.00)
    conn.close()

    init_db(db_path)

    conn = _connect(db_path)
    row = conn.execute("SELECT category FROM transactions WHERE fingerprint = 'fp1'").fetchone()
    conn.close()
    assert row["category"] == "Others"


def test_correctly_directed_category_is_left_alone(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)

    conn = _connect(db_path)
    _seed_transaction(conn, category="Transport", amount=-12.50)
    conn.close()

    init_db(db_path)

    conn = _connect(db_path)
    row = conn.execute("SELECT category FROM transactions WHERE fingerprint = 'fp1'").fetchone()
    conn.close()
    assert row["category"] == "Transport"


def test_rules_direction_backfilled_from_category_for_pre_existing_dbs(tmp_path):
    """Simulates a DB created before rules.direction existed: a category
    rule created back then must come back with the same direction its
    category already had (not silently dropped to the outflow column
    default) once the column is added on next launch."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    conn = _connect(db_path)
    conn.execute("ALTER TABLE rules DROP COLUMN direction")
    conn.execute(
        "INSERT INTO rules (priority, match_pattern, target_category, is_exclusion_rule) "
        "VALUES (1, 'PAYROLL', 'Salary', 0)"
    )
    conn.commit()
    conn.close()

    init_db(db_path)  # simulates the app restarting on a pre-direction-column DB

    conn = _connect(db_path)
    row = conn.execute("SELECT direction FROM rules WHERE match_pattern = 'PAYROLL'").fetchone()
    conn.close()
    assert row["direction"] == "inflow"


def test_contacts_category_split_backfills_from_old_single_column_by_direction(tmp_path):
    """Simulates a DB created before the outflow/inflow split (a single NOT
    NULL default_category) - each contact's existing value must land under
    whichever new column matches its own category's direction, the other
    left null, and the old column itself must be gone afterward (not just
    ignored)."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    conn = _connect(db_path)
    conn.execute("ALTER TABLE contacts DROP COLUMN default_category_outflow")
    conn.execute("ALTER TABLE contacts DROP COLUMN default_category_inflow")
    conn.execute("ALTER TABLE contacts ADD COLUMN default_category TEXT NOT NULL DEFAULT ''")
    conn.execute("INSERT INTO contacts (name, default_category) VALUES ('Auntie Mei', 'Paynow')")
    conn.execute("INSERT INTO contacts (name, default_category) VALUES ('Employer Co', 'Salary')")
    conn.commit()
    conn.close()

    init_db(db_path)  # simulates the app restarting on a pre-split DB

    conn = _connect(db_path)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(contacts)").fetchall()}
    assert "default_category" not in columns

    mei = conn.execute("SELECT * FROM contacts WHERE name = 'Auntie Mei'").fetchone()
    assert mei["default_category_outflow"] == "Paynow"
    assert mei["default_category_inflow"] is None

    employer = conn.execute("SELECT * FROM contacts WHERE name = 'Employer Co'").fetchone()
    assert employer["default_category_outflow"] is None
    assert employer["default_category_inflow"] == "Salary"
    conn.close()
