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
    # Only two ~30-degree gaps were left in the wheel: 205 (between Transport
    # and Education) and 45 (between Food & Drink and Bills & Fees). Both put
    # the new hue 15 degrees from each neighbour, so the tie breaks on which
    # pair of neighbours it is worse to sit between - and Food & Drink and
    # Bills & Fees are on far more rows than Transport and Education are.
    # The wider gaps at 70 and 250 aren't available: index.css spends those
    # on the warning and needs-review tokens, which appear alongside category
    # badges (see the note there on why review-blue is not warning-amber).
    # 15 degrees is a subtle separation, which is survivable here because
    # colour has never been the only channel - every badge carries its icon
    # and its name, and the plane/bus and plane/graduation-cap pairs are not
    # confusable at all.
    ("Travel", 205, "plane", False, "outflow"),
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
# rule.target_category has no amount to check against, so it keeps pointing
# at the outflow name (categorize() simply skips a rule whose category
# direction doesn't match, falling through to the next tier). Contacts don't
# need this redirect at all: default_category_outflow/_inflow are already
# independently direction-scoped columns (see _migrate_contacts_category_split),
# not a single ambiguous value that needs live redirecting.
_AMBIGUOUS_CATEGORY_INFLOW_REDIRECT = {
    "Investing": "Investment Income",
    "Paynow": "Paynow Received",
    "Others": "Other Income",
}


def _apply_category_renames(conn: sqlite3.Connection) -> None:
    for old, new in _CATEGORY_RENAMES.items():
        conn.execute("UPDATE transactions SET category = ? WHERE category = ?", (new, old))
        conn.execute("UPDATE contacts SET default_category_outflow = ? WHERE default_category_outflow = ?", (new, old))
        conn.execute("UPDATE contacts SET default_category_inflow = ? WHERE default_category_inflow = ?", (new, old))
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


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> bool:
    existing_columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing_columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
        return True
    return False


def migrate_schema(conn: sqlite3.Connection) -> bool:
    """CREATE TABLE IF NOT EXISTS in schema.sql only covers fresh installs -
    a DB created before a column existed needs an explicit ALTER TABLE.
    Returns whether rules.direction was just added, so run_all() can
    backfill it from each rule's target category afterward - it can't be
    done here because that backfill needs categories.direction to already
    hold real per-category values, and reconcile_categories() (which
    populates those) hasn't run yet at this point."""
    _add_column_if_missing(conn, "rules", "is_default", "is_default BOOLEAN DEFAULT 0")
    _add_column_if_missing(conn, "rules", "display_label", "display_label TEXT")
    _add_column_if_missing(conn, "transactions", "matched_label", "matched_label TEXT")
    _add_column_if_missing(conn, "categories", "icon", "icon TEXT")
    _add_column_if_missing(conn, "categories", "is_hidden", "is_hidden BOOLEAN DEFAULT 0")
    _add_column_if_missing(conn, "accounts", "is_card", "is_card BOOLEAN DEFAULT 0")
    _add_column_if_missing(conn, "categories", "direction", "direction TEXT NOT NULL DEFAULT 'outflow'")
    _add_column_if_missing(conn, "transactions", "source_filename", "source_filename TEXT")
    _add_column_if_missing(conn, "contacts", "default_category_outflow", "default_category_outflow TEXT")
    _add_column_if_missing(conn, "contacts", "default_category_inflow", "default_category_inflow TEXT")
    return _add_column_if_missing(conn, "rules", "direction", "direction TEXT NOT NULL DEFAULT 'outflow'")


def _migrate_contacts_category_split(conn: sqlite3.Connection) -> None:
    """One-time rebuild for a DB that predates the outflow/inflow split
    (schema.sql's contacts table used to have a single NOT NULL
    default_category) - _add_column_if_missing alone can't do this one,
    since ADD COLUMN can't relax an existing NOT NULL constraint, so this
    backfills the two new columns from the old one's value and then drops
    it outright (SQLite's ALTER TABLE ... DROP COLUMN, supported since
    3.35 - this project ships 3.45+, see db.py's sqlite3 usage). Must run
    before _apply_category_renames, which writes the new columns directly
    and no longer knows the old one exists; uses _CATEGORY_DIRECTIONS (a
    static map, not the categories table) so it doesn't have to wait for
    reconcile_categories() to run first - a category's direction never
    depends on live DB state, only on default_rules.py's own definition."""
    existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(contacts)").fetchall()}
    if "default_category" not in existing_columns:
        return
    for row in conn.execute("SELECT id, default_category FROM contacts WHERE default_category IS NOT NULL").fetchall():
        column = (
            "default_category_inflow"
            if _CATEGORY_DIRECTIONS.get(row["default_category"], "outflow") == "inflow"
            else "default_category_outflow"
        )
        conn.execute(f"UPDATE contacts SET {column} = ? WHERE id = ?", (row["default_category"], row["id"]))
    conn.execute("ALTER TABLE contacts DROP COLUMN default_category")


def _backfill_rule_directions_from_category(conn: sqlite3.Connection) -> None:
    """One-time backfill for DBs that predate rules.direction. A
    category-assigning rule's direction is just the direction of the
    category it already assigns - it could never actually have applied to
    the opposite direction anyway (see engine/rules.py's
    _category_direction check), so this restores exactly the same
    behavior those rules already had rather than dropping them to the
    'outflow' column default. Exclusion rules have no category to infer a
    direction from - they were never direction-scoped before this field
    existed, so they keep that default and the user can flip specific ones
    to inflow if that's wrong for them."""
    conn.execute(
        """
        UPDATE rules SET direction = (
            SELECT direction FROM categories WHERE categories.name = rules.target_category
        )
        WHERE is_exclusion_rule = 0
          AND EXISTS (SELECT 1 FROM categories WHERE categories.name = rules.target_category)
        """
    )


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


_CATEGORY_DIRECTIONS = {name: direction for name, *_, direction in DEFAULT_CATEGORIES}


def reconcile_default_rules(conn: sqlite3.Connection) -> None:
    """Default rules are a pure function of default_rules.py, not user data -
    fully replacing them on every startup (rather than seeding once and
    skipping thereafter) is what lets adding a new pattern to the bank reach
    already-initialized DBs without a one-off migration script."""
    conn.execute("DELETE FROM rules WHERE is_default = 1")
    conn.executemany(
        "INSERT INTO rules (priority, match_pattern, target_category, direction, is_exclusion_rule, is_default, "
        "display_label) VALUES (?, ?, ?, ?, 0, 1, ?)",
        [
            (10000 + i, pattern, category, _CATEGORY_DIRECTIONS.get(category, "outflow"), label)
            for i, (pattern, category, label) in enumerate(iter_default_rules())
        ],
    )


def run_all(conn: sqlite3.Connection) -> None:
    """Called once per db.init_db(). Order matters: schema DDL before data
    reconciliation, and renames/direction-redirects before reconcile_categories()
    so a just-migrated row isn't immediately re-created under its old name."""
    rules_direction_just_added = migrate_schema(conn)
    _migrate_contacts_category_split(conn)
    _apply_category_renames(conn)
    _migrate_ambiguous_category_directions(conn)
    _migrate_direction_mismatched_transactions(conn)
    reconcile_categories(conn)
    if rules_direction_just_added:
        _backfill_rule_directions_from_category(conn)
    reconcile_default_rules(conn)
