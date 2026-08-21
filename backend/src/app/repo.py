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

from app.engine import paynow
from app.engine.naming import extract_display_name


def fetch_active_rules(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM rules ORDER BY priority ASC").fetchall()


def fetch_category_directions(conn: sqlite3.Connection) -> dict[str, str]:
    return {row["name"]: row["direction"] for row in conn.execute("SELECT name, direction FROM categories").fetchall()}


def fetch_ai_target_categories(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """(name, direction) pairs the AI is allowed to suggest - excludes the
    hidden Others/Other Income fallback (suggesting them would be a no-op)
    and the two Paynow categories (those are only ever derived from a
    scheme-marker/contact match, never a merchant guess - see engine/paynow.py)."""
    return [
        (row["name"], row["direction"])
        for row in conn.execute("SELECT name, direction FROM categories WHERE is_hidden = 0").fetchall()
        if not paynow.is_paynow_category(row["name"])
    ]


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


def apply_save_as_rule_and_contact(
    conn: sqlite3.Connection,
    *,
    raw_description: str,
    category: str,
    subcategory: str | None,
    save_as_rule: bool,
    rule_pattern: str | None,
    rule_priority: int | None = None,
    save_as_contact: bool,
    contact_name: str | None,
    contact_identifier: str | None,
) -> int | None:
    """The "Save as rule"/"Save as contact mapping" quick actions shared by
    the staging and recategorize row-update endpoints (see
    routers/statements.py::update_staging_row and
    routers/transactions.py::update_recategorize_row) - previously
    reimplemented separately in each. Returns the resolved contact_id when
    save_as_contact is set, else None; the caller decides what to do with it
    (staging stores it on the in-memory row, recategorize on its row too)."""
    if save_as_rule:
        pattern = rule_pattern or extract_display_name(raw_description)
        priority = rule_priority if rule_priority is not None else next_user_rule_priority(conn)
        insert_rule(
            conn,
            priority=priority,
            match_pattern=pattern,
            target_category=category,
            target_subcategory=subcategory,
        )

    if not save_as_contact:
        return None
    identifier = contact_identifier or extract_display_name(raw_description)
    name = contact_name or identifier
    contact_id = find_contact_id_by_identifier(conn, identifier)
    if contact_id is None:
        contact_id = insert_contact(
            conn, name=name, default_category=category, default_subcategory=subcategory, identifiers=[identifier]
        )
    return contact_id


def replace_contact_identifiers(conn: sqlite3.Connection, contact_id: int, identifiers: list[str]) -> None:
    conn.execute("DELETE FROM contact_identifiers WHERE contact_id = ?", (contact_id,))
    for identifier in identifiers:
        conn.execute(
            "INSERT INTO contact_identifiers (contact_id, identifier) VALUES (?, ?)",
            (contact_id, identifier),
        )
