"""Category-table lookups, and the save-as-rule/save-as-contact
orchestration that spans both the rule catalog and the contact directory.

Rule creation/priority-allocation/direction-derivation lives in
rule_catalog.py; contact creation/identifier-lookup lives in
contact_directory.py (see CONTEXT.md) - this module is what's left once
those two are their own deep modules: pure `categories`-table reads, plus
apply_save_as_rule_and_contact, which is genuinely cross-cutting (a single
"Save as rule" + "Save as contact mapping" quick action can create both a
rule and a contact in one call, so it can't live wholly inside either
module without the other importing it back).
"""

import sqlite3

from app import contact_directory, rule_catalog
from app.engine import paynow
from app.engine.naming import extract_display_name


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
        priority = rule_priority if rule_priority is not None else rule_catalog.next_user_rule_priority(conn)
        rule_catalog.insert_rule(
            conn,
            priority=priority,
            match_pattern=pattern,
            target_category=category,
            target_subcategory=subcategory,
            direction=rule_catalog.category_direction(conn, category),
        )

    if not save_as_contact:
        return None
    identifier = contact_identifier or extract_display_name(raw_description)
    name = contact_name or identifier
    contact_id = contact_directory.find_contact_id_by_identifier(conn, identifier)
    if contact_id is None:
        contact_id = contact_directory.insert_contact(
            conn, name=name, default_category=category, default_subcategory=subcategory, identifiers=[identifier]
        )
    return contact_id
