"""Rule catalog: creation, priority allocation, and direction derivation for
categorization rules (the `rules` table read by engine/rules.py::categorize()).

Extracted out of repo.py's undifferentiated grab bag - see CONTEXT.md's Rule
catalog entry. Lives outside engine/ deliberately, same reasoning as
repo.py's own docstring: engine/ is pure (no DB access), this module isn't.
"""

import sqlite3


def fetch_active_rules(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM rules ORDER BY priority ASC").fetchall()


def next_user_rule_priority(conn: sqlite3.Connection) -> int:
    max_priority = conn.execute("SELECT MAX(priority) FROM rules WHERE is_default = 0").fetchone()[0]
    return (max_priority or 0) + 1


def category_direction(conn: sqlite3.Connection, category: str | None, default: str = "outflow") -> str:
    """The live direction ('inflow'/'outflow') of a named category, or
    `default` if the category is unknown - used to derive a rule's own
    direction from whichever category it assigns, so a category-assigning
    rule can never independently drift out of sync with the category it
    targets (see insert_rule's `direction` param and engine/rules.py's
    exclusion-rule direction check)."""
    if category is None:
        return default
    row = conn.execute("SELECT direction FROM categories WHERE name = ?", (category,)).fetchone()
    return row["direction"] if row else default


def insert_rule(
    conn: sqlite3.Connection,
    *,
    priority: int,
    match_pattern: str,
    target_category: str | None,
    target_subcategory: str | None = None,
    is_exclusion_rule: bool = False,
    exclusion_reason: str | None = None,
    direction: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO rules (priority, match_pattern, target_category, target_subcategory, "
        "is_exclusion_rule, exclusion_reason, direction) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (priority, match_pattern, target_category, target_subcategory, is_exclusion_rule, exclusion_reason, direction),
    )
    return cur.lastrowid
