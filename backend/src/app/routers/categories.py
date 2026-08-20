from fastapi import APIRouter

from app.db import get_conn
from app.models import CategoryCreateRequest, CategoryOut

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM categories ORDER BY sort_order").fetchall()
        return [CategoryOut(**dict(r)) for r in rows]


@router.post("", response_model=CategoryOut)
def create_category(body: CategoryCreateRequest):
    with get_conn() as conn:
        max_sort = conn.execute("SELECT MAX(sort_order) FROM categories").fetchone()[0]
        cur = conn.execute(
            "INSERT INTO categories (name, hue, sort_order) VALUES (?, ?, ?)",
            (body.name, body.hue, (max_sort or 0) + 1),
        )
        row = conn.execute("SELECT * FROM categories WHERE id = ?", (cur.lastrowid,)).fetchone()
        return CategoryOut(**dict(row))
