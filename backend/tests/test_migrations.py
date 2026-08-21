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
