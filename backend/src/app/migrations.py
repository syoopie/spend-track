"""Schema/data migrations run on every db.init_db() call.

Split out of db.py because this file's responsibilities (DDL column
migration, category reconciliation, default-rule reconciliation, category
renames) kept growing independently of db.py's actual job (connection
lifecycle) - every categorization feature added this session landed
another top-level function in what used to be db.py.
"""

import sqlite3

from app.engine.default_rules import iter_default_rules

# (name, hue, icon, is_hidden, direction) - a category is locked to one
# direction; "Investing"/"Paynow"/"Others" used to silently serve both
# (an interest credit and a stock purchase both landed under "Investing"),
# which is exactly the confusion categories.direction exists to prevent.
# Their inflow-side siblings below are separate categories, not a rename.
DEFAULT_CATEGORIES = [
    ("Sports & Hobbies", 150, "dumbbell", False, "outflow"),
    ("Beauty", 320, "sparkles", False, "outflow"),
    ("Food & Drink", 30, "utensils", False, "outflow"),
    ("Shopping", 280, "shopping-bag", False, "outflow"),
    ("Transport", 190, "bus", False, "outflow"),
    ("Home", 90, "home", False, "outflow"),
    ("Bills & Fees", 60, "receipt", False, "outflow"),
    ("Entertainment", 260, "clapperboard", False, "outflow"),
    ("Healthcare", 0, "heart-pulse", False, "outflow"),
    ("Education", 220, "graduation-cap", False, "outflow"),
    ("Groceries", 230, "shopping-cart", False, "outflow"),
    ("Investing", 170, "trending-up", False, "outflow"),
    ("Paynow", 20, "send", False, "outflow"),
    ("Others", None, "more-horizontal", True, "outflow"),
    ("Salary", 130, "banknote", False, "inflow"),
    ("Refunds & Reimbursements", 105, "undo-2", False, "inflow"),
    ("Investment Income", 300, "piggy-bank", False, "inflow"),
    ("Paynow Received", 340, "download", False, "inflow"),
    ("Other Income", None, "wallet", True, "inflow"),
]

_OLD_CATEGORY_NAMES_TO_DROP = ("Dining", "Bills & Utilities")

# name changes to an already-shipped category - unlike _OLD_CATEGORY_NAMES_TO_DROP
# (dropped outright, no successor), rows already using the old name in
# transactions/contacts/rules need to be repointed at the new one or they'd
# silently fall off the visible category list.
_CATEGORY_RENAMES = {"PayNow Transfers": "Paynow"}

# These three categories used to serve both directions before categories
# gained a locked `direction`. Only *transactions* get migrated here -
# contact.default_category/rule.target_category have no amount to check
# against, so they keep pointing at the outflow name; categorize() redirects
# Paynow <-> Paynow Received live per-transaction based on the actual
# amount, and simply skips a rule/contact whose category direction doesn't
# match (falling through to the next tier) for the other two.
_AMBIGUOUS_CATEGORY_INFLOW_REDIRECT = {
    "Investing": "Investment Income",
    "Paynow": "Paynow Received",
    "Others": "Other Income",
}


def _apply_category_renames(conn: sqlite3.Connection) -> None:
    for old, new in _CATEGORY_RENAMES.items():
        conn.execute("UPDATE transactions SET category = ? WHERE category = ?", (new, old))
        conn.execute("UPDATE contacts SET default_category = ? WHERE default_category = ?", (new, old))
        conn.execute("UPDATE rules SET target_category = ? WHERE target_category = ?", (new, old))
        conn.execute("DELETE FROM categories WHERE name = ?", (old,))


def _migrate_ambiguous_category_directions(conn: sqlite3.Connection) -> None:
    for old, new in _AMBIGUOUS_CATEGORY_INFLOW_REDIRECT.items():
        conn.execute(
            "UPDATE transactions SET category = ? WHERE category = ? AND amount > 0",
            (new, old),
        )


def _migrate_direction_mismatched_transactions(conn: sqlite3.Connection) -> None:
    """Catch-all for every other category a transaction can be stuck under
    that contradicts its own amount's direction (e.g. a pre-direction-lock
    rule matched "Transport" on a refund credit) - unlike the three
    categories above, there's no natural same-topic sibling to redirect to,
    so this falls back to the generic hidden Others/Other Income bucket."""
    outflow_names = [name for name, *_, direction in DEFAULT_CATEGORIES if direction == "outflow"]
    inflow_names = [name for name, *_, direction in DEFAULT_CATEGORIES if direction == "inflow"]
    conn.execute(
        f"UPDATE transactions SET category = 'Other Income' "
        f"WHERE amount > 0 AND category IN ({','.join('?' * len(outflow_names))})",
        outflow_names,
    )
    conn.execute(
        f"UPDATE transactions SET category = 'Others' "
        f"WHERE amount <= 0 AND category IN ({','.join('?' * len(inflow_names))})",
        inflow_names,
    )


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    existing_columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing_columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def migrate_schema(conn: sqlite3.Connection) -> None:
    """CREATE TABLE IF NOT EXISTS in schema.sql only covers fresh installs -
    a DB created before a column existed needs an explicit ALTER TABLE."""
    _add_column_if_missing(conn, "rules", "is_default", "is_default BOOLEAN DEFAULT 0")
    _add_column_if_missing(conn, "rules", "display_label", "display_label TEXT")
    _add_column_if_missing(conn, "transactions", "matched_label", "matched_label TEXT")
    _add_column_if_missing(conn, "categories", "icon", "icon TEXT")
    _add_column_if_missing(conn, "categories", "is_hidden", "is_hidden BOOLEAN DEFAULT 0")
    _add_column_if_missing(conn, "accounts", "is_card", "is_card BOOLEAN DEFAULT 0")
    _add_column_if_missing(conn, "categories", "direction", "direction TEXT NOT NULL DEFAULT 'outflow'")


def reconcile_categories(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "DELETE FROM categories WHERE name = ?",
        [(name,) for name in _OLD_CATEGORY_NAMES_TO_DROP],
    )
    conn.executemany(
        """
        INSERT INTO categories (name, hue, icon, is_hidden, sort_order, direction) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            hue = excluded.hue, icon = excluded.icon, is_hidden = excluded.is_hidden,
            sort_order = excluded.sort_order, direction = excluded.direction
        """,
        [
            (name, hue, icon, is_hidden, i, direction)
            for i, (name, hue, icon, is_hidden, direction) in enumerate(DEFAULT_CATEGORIES)
        ],
    )


def reconcile_default_rules(conn: sqlite3.Connection) -> None:
    """Default rules are a pure function of default_rules.py, not user data -
    fully replacing them on every startup (rather than seeding once and
    skipping thereafter) is what lets adding a new pattern to the bank reach
    already-initialized DBs without a one-off migration script."""
    conn.execute("DELETE FROM rules WHERE is_default = 1")
    conn.executemany(
        "INSERT INTO rules (priority, match_pattern, target_category, is_exclusion_rule, is_default, display_label) "
        "VALUES (?, ?, ?, 0, 1, ?)",
        [
            (10000 + i, pattern, category, label)
            for i, (pattern, category, label) in enumerate(iter_default_rules())
        ],
    )


def run_all(conn: sqlite3.Connection) -> None:
    """Called once per db.init_db(). Order matters: schema DDL before data
    reconciliation, and renames/direction-redirects before reconcile_categories()
    so a just-migrated row isn't immediately re-created under its old name."""
    migrate_schema(conn)
    _apply_category_renames(conn)
    _migrate_ambiguous_category_directions(conn)
    _migrate_direction_mismatched_transactions(conn)
    reconcile_categories(conn)
    reconcile_default_rules(conn)
