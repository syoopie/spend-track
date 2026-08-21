import sqlite3
from contextlib import contextmanager
from importlib import resources
from pathlib import Path

from app.config import get_db_path
from app.migrations import run_all


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
        run_all(conn)
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
