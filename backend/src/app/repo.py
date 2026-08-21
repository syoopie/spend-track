"""Small DB-query/write helpers shared across routers.

These live outside engine/ deliberately - engine/ is pure (no DB access,
takes data as arguments, see its own module docstrings). This module
exists specifically to stop routers from re-implementing the same
SELECT/INSERT independently. Before it existed, fetch_active_rules/
fetch_contact_identifiers were copy-pasted verbatim into both
statements.py and transactions.py, and had to be edited in lockstep when
categorize() gained its `amount` parameter; insert_contact's shape was
independently reimplemented 4 times (contacts.py's create/update/CSV
import, statements.py's staging quick-apply) and insert_rule twice.
"""

import sqlite3


def fetch_active_rules(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM rules ORDER BY priority ASC").fetchall()


def fetch_contact_identifiers(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT ci.identifier AS identifier, c.id AS contact_id, c.name AS name,
               c.default_category AS default_category, c.default_subcategory AS default_subcategory
        FROM contact_identifiers ci JOIN contacts c ON c.id = ci.contact_id
        """
    ).fetchall()


def next_user_rule_priority(conn: sqlite3.Connection) -> int:
    max_priority = conn.execute("SELECT MAX(priority) FROM rules WHERE is_default = 0").fetchone()[0]
    return (max_priority or 0) + 1


def insert_rule(
    conn: sqlite3.Connection,
    *,
    priority: int,
    match_pattern: str,
    target_category: str | None,
    target_subcategory: str | None = None,
    is_exclusion_rule: bool = False,
    exclusion_reason: str | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO rules (priority, match_pattern, target_category, target_subcategory, "
        "is_exclusion_rule, exclusion_reason) VALUES (?, ?, ?, ?, ?, ?)",
        (priority, match_pattern, target_category, target_subcategory, is_exclusion_rule, exclusion_reason),
    )
    return cur.lastrowid


def find_contact_id_by_identifier(conn: sqlite3.Connection, identifier: str) -> int | None:
    row = conn.execute(
        "SELECT contact_id FROM contact_identifiers WHERE identifier = ?", (identifier,)
    ).fetchone()
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
