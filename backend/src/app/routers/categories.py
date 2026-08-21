from fastapi import APIRouter

from app.db import get_conn
from app.models import CategoryCreateRequest, CategoryOut

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories(include_hidden: bool = False):
    with get_conn() as conn:
        query = "SELECT * FROM categories" + ("" if include_hidden else " WHERE is_hidden = 0") + " ORDER BY sort_order"
        rows = conn.execute(query).fetchall()
        return [CategoryOut(**dict(r)) for r in rows]


@router.post("", response_model=CategoryOut)
def create_category(body: CategoryCreateRequest):
    with get_conn() as conn:
        max_sort = conn.execute("SELECT MAX(sort_order) FROM categories").fetchone()[0]
        cur = conn.execute(
            "INSERT INTO categories (name, hue, icon, sort_order, direction) VALUES (?, ?, ?, ?, ?)",
            (body.name, body.hue, body.icon, (max_sort or 0) + 1, body.direction),
        )
        row = conn.execute("SELECT * FROM categories WHERE id = ?", (cur.lastrowid,)).fetchone()
        return CategoryOut(**dict(row))
