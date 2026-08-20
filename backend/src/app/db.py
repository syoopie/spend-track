import sqlite3
from contextlib import contextmanager
from importlib import resources
from pathlib import Path

from app.config import get_db_path

DEFAULT_CATEGORIES = [
    ("Groceries", 230),
    ("Dining", 340),
    ("Transport", 190),
    ("Shopping", 280),
    ("Bills & Utilities", 60),
    ("PayNow Transfers", 20),
    ("Others", None),
]


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | None = None) -> None:
    db_path = db_path or get_db_path()
    conn = _connect(db_path)
    try:
        schema_sql = resources.files("app").joinpath("schema.sql").read_text()
        conn.executescript(schema_sql)
        existing = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if existing == 0:
            conn.executemany(
                "INSERT INTO categories (name, hue, sort_order) VALUES (?, ?, ?)",
                [(name, hue, i) for i, (name, hue) in enumerate(DEFAULT_CATEGORIES)],
            )
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
