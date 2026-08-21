import sqlite3
from contextlib import contextmanager
from importlib import resources
from pathlib import Path

from app.config import get_db_path
from app.engine.default_rules import iter_default_rules

# (name, hue, icon, is_hidden) - "PayNow Transfers" and "Others" are kept
# from the old 7-category set; "Others" is a hidden internal fallback, never
# shown in category pickers. "Dining"/"Bills & Utilities" have no equivalent
# here and are dropped by the reconciliation below.
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
    ("PayNow Transfers", 20, "send", False),
    ("Others", None, "more-horizontal", True),
]

_OLD_CATEGORY_NAMES_TO_DROP = ("Dining", "Bills & Utilities")


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


def _seed_default_rules(conn: sqlite3.Connection) -> None:
    existing = conn.execute("SELECT COUNT(*) FROM rules WHERE is_default = 1").fetchone()[0]
    if existing:
        return
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
        _reconcile_categories(conn)
        _seed_default_rules(conn)
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
