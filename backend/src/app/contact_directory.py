"""Contact directory: creation and PayNow-identifier lookup for contacts
(the `contacts`/`contact_identifiers` tables).

Extracted out of repo.py's undifferentiated grab bag - see CONTEXT.md's
Contact directory entry. Lives outside engine/ deliberately, same reasoning
as repo.py's own docstring: engine/ is pure (no DB access), this module isn't.
"""

import sqlite3


def fetch_contact_identifiers(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT ci.identifier AS identifier, c.id AS contact_id, c.name AS name,
               c.default_category AS default_category, c.default_subcategory AS default_subcategory
        FROM contact_identifiers ci JOIN contacts c ON c.id = ci.contact_id
        """
    ).fetchall()


def find_contact_id_by_identifier(conn: sqlite3.Connection, identifier: str) -> int | None:
    row = conn.execute("SELECT contact_id FROM contact_identifiers WHERE identifier = ?", (identifier,)).fetchone()
    return row["contact_id"] if row else None


def insert_contact(
    conn: sqlite3.Connection,
    *,
    name: str,
    default_category: str | None,
    default_subcategory: str | None = None,
    identifiers: list[str] = (),
) -> int:
    cur = conn.execute(
        "INSERT INTO contacts (name, default_category, default_subcategory) VALUES (?, ?, ?)",
        (name, default_category, default_subcategory),
    )
    contact_id = cur.lastrowid
    for identifier in identifiers:
        conn.execute(
            "INSERT INTO contact_identifiers (contact_id, identifier) VALUES (?, ?)",
            (contact_id, identifier),
        )
    return contact_id


def replace_contact_identifiers(conn: sqlite3.Connection, contact_id: int, identifiers: list[str]) -> None:
    conn.execute("DELETE FROM contact_identifiers WHERE contact_id = ?", (contact_id,))
    for identifier in identifiers:
        conn.execute(
            "INSERT INTO contact_identifiers (contact_id, identifier) VALUES (?, ?)",
            (contact_id, identifier),
        )
