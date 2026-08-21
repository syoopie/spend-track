import sqlite3
from contextlib import contextmanager
from importlib import resources
from pathlib import Path

from app.config import get_db_path
from app.engine.default_rules import iter_default_rules

# (name, hue, icon, is_hidden) - "Paynow" and "Others" are kept from the old
# 7-category set; "Others" is a hidden internal fallback, never shown in
# category pickers. "Dining"/"Bills & Utilities" have no equivalent here and
# are dropped by the reconciliation below.
DEFAULT_CATEGORIES = [
    ("Sports & Hobbies", 150, "dumbbell", False),
    ("Beauty", 320, "sparkles", False),
    ("Food & Drink", 30, "utensils", False),
    ("Shopping", 280, "shopping-bag", False),
    ("Transport", 190, "bus", False),
    ("Home", 90, "home", False),
    ("Bills & Fees", 60, "receipt", False),
    ("Entertainment", 260, "clapperboard", False),
    ("Healthcare", 0, "heart-pulse", False),
    ("Education", 220, "graduation-cap", False),
    ("Groceries", 230, "shopping-cart", False),
    ("Salary", 130, "banknote", False),
    ("Investing", 170, "trending-up", False),
    ("Paynow", 20, "send", False),
    ("Others", None, "more-horizontal", True),
]

_OLD_CATEGORY_NAMES_TO_DROP = ("Dining", "Bills & Utilities")

# name changes to an already-shipped category - unlike _OLD_CATEGORY_NAMES_TO_DROP
# (dropped outright, no successor), rows already using the old name in
# transactions/contacts/rules need to be repointed at the new one or they'd
# silently fall off the visible category list.
_CATEGORY_RENAMES = {"PayNow Transfers": "Paynow"}


def _apply_category_renames(conn: sqlite3.Connection) -> None:
    for old, new in _CATEGORY_RENAMES.items():
        conn.execute("UPDATE transactions SET category = ? WHERE category = ?", (new, old))
        conn.execute("UPDATE contacts SET default_category = ? WHERE default_category = ?", (new, old))
        conn.execute("UPDATE rules SET target_category = ? WHERE target_category = ?", (new, old))
        conn.execute("DELETE FROM categories WHERE name = ?", (old,))


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    existing_columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing_columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """CREATE TABLE IF NOT EXISTS in schema.sql only covers fresh installs -
    a DB created before a column existed needs an explicit ALTER TABLE."""
    _add_column_if_missing(conn, "rules", "is_default", "is_default BOOLEAN DEFAULT 0")
    _add_column_if_missing(conn, "rules", "display_label", "display_label TEXT")
    _add_column_if_missing(conn, "transactions", "matched_label", "matched_label TEXT")
    _add_column_if_missing(conn, "categories", "icon", "icon TEXT")
    _add_column_if_missing(conn, "categories", "is_hidden", "is_hidden BOOLEAN DEFAULT 0")
    _add_column_if_missing(conn, "accounts", "is_card", "is_card BOOLEAN DEFAULT 0")


def _reconcile_categories(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "DELETE FROM categories WHERE name = ?",
        [(name,) for name in _OLD_CATEGORY_NAMES_TO_DROP],
    )
    conn.executemany(
        """
        INSERT INTO categories (name, hue, icon, is_hidden, sort_order) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            hue = excluded.hue, icon = excluded.icon, is_hidden = excluded.is_hidden,
            sort_order = excluded.sort_order
        """,
        [(name, hue, icon, is_hidden, i) for i, (name, hue, icon, is_hidden) in enumerate(DEFAULT_CATEGORIES)],
    )


def _reconcile_default_rules(conn: sqlite3.Connection) -> None:
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


def init_db(db_path: Path | None = None) -> None:
    db_path = db_path or get_db_path()
    conn = _connect(db_path)
    try:
        schema_sql = resources.files("app").joinpath("schema.sql").read_text()
        conn.executescript(schema_sql)
        _migrate_schema(conn)
        _apply_category_renames(conn)
        _reconcile_categories(conn)
        _reconcile_default_rules(conn)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_conn():
    db_path = get_db_path()
    conn = _connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
