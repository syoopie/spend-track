from app import contact_directory
from app.db import _connect, init_db


def make_conn(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return _connect(db_path)


def test_insert_contact_persists_identifiers(tmp_path):
    conn = make_conn(tmp_path)
    contact_id = contact_directory.insert_contact(
        conn,
        name="Auntie Mei",
        default_category="Paynow",
        default_subcategory=None,
        identifiers=["+65 9123 4567", "auntiemei"],
    )
    conn.commit()

    row = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
    assert row["name"] == "Auntie Mei"
    assert row["default_category"] == "Paynow"

    identifiers = {
        r["identifier"]
        for r in conn.execute(
            "SELECT identifier FROM contact_identifiers WHERE contact_id = ?", (contact_id,)
        ).fetchall()
    }
    assert identifiers == {"+65 9123 4567", "auntiemei"}


def test_find_contact_id_by_identifier_returns_none_when_unmapped(tmp_path):
    conn = make_conn(tmp_path)
    assert contact_directory.find_contact_id_by_identifier(conn, "+65 9999 9999") is None


def test_find_contact_id_by_identifier_finds_the_mapped_contact(tmp_path):
    conn = make_conn(tmp_path)
    contact_id = contact_directory.insert_contact(
        conn, name="Auntie Mei", default_category="Paynow", identifiers=["+65 9123 4567"]
    )
    conn.commit()

    assert contact_directory.find_contact_id_by_identifier(conn, "+65 9123 4567") == contact_id


def test_replace_contact_identifiers_swaps_the_full_set(tmp_path):
    conn = make_conn(tmp_path)
    contact_id = contact_directory.insert_contact(
        conn, name="Auntie Mei", default_category="Paynow", identifiers=["old-one", "old-two"]
    )
    conn.commit()

    contact_directory.replace_contact_identifiers(conn, contact_id, ["new-one"])
    conn.commit()

    identifiers = {
        r["identifier"]
        for r in conn.execute(
            "SELECT identifier FROM contact_identifiers WHERE contact_id = ?", (contact_id,)
        ).fetchall()
    }
    assert identifiers == {"new-one"}


def test_fetch_contact_identifiers_joins_contact_fields(tmp_path):
    conn = make_conn(tmp_path)
    contact_id = contact_directory.insert_contact(
        conn,
        name="Auntie Mei",
        default_category="Paynow",
        default_subcategory="Family",
        identifiers=["+65 9123 4567"],
    )
    conn.commit()

    rows = contact_directory.fetch_contact_identifiers(conn)
    assert len(rows) == 1
    row = rows[0]
    assert row["identifier"] == "+65 9123 4567"
    assert row["contact_id"] == contact_id
    assert row["name"] == "Auntie Mei"
    assert row["default_category"] == "Paynow"
    assert row["default_subcategory"] == "Family"
