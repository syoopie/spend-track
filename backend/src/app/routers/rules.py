from fastapi import APIRouter, HTTPException

from app.db import get_conn
from app.models import RuleCreateRequest, RuleOut, RuleReorderRequest, RuleUpdateRequest

router = APIRouter(prefix="/api/rules", tags=["rules"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "RULE_NOT_FOUND", "message": "No rule with that id."})


def _row_to_out(row) -> RuleOut:
    return RuleOut(
        id=row["id"],
        priority=row["priority"],
        match_pattern=row["match_pattern"],
        target_category=row["target_category"],
        target_subcategory=row["target_subcategory"],
        is_exclusion_rule=bool(row["is_exclusion_rule"]),
        exclusion_reason=row["exclusion_reason"],
    )


@router.get("", response_model=list[RuleOut])
def list_rules():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM rules ORDER BY priority ASC").fetchall()
        return [_row_to_out(r) for r in rows]


@router.post("", response_model=RuleOut)
def create_rule(body: RuleCreateRequest):
    with get_conn() as conn:
        priority = body.priority
        if priority is None:
            max_priority = conn.execute("SELECT MAX(priority) FROM rules").fetchone()[0]
            priority = (max_priority or 0) + 1
        # target_category is NOT NULL per TECHNICAL_SPEC.md's schema even
        # though exclusion rules don't use it - default to "Others" for those.
        target_category = body.target_category or "Others"
        cur = conn.execute(
            "INSERT INTO rules (priority, match_pattern, target_category, target_subcategory, "
            "is_exclusion_rule, exclusion_reason) VALUES (?, ?, ?, ?, ?, ?)",
            (
                priority,
                body.match_pattern,
                target_category,
                body.target_subcategory,
                body.is_exclusion_rule,
                body.exclusion_reason,
            ),
        )
        row = conn.execute("SELECT * FROM rules WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _row_to_out(row)


@router.patch("/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: int, body: RuleUpdateRequest):
    with get_conn() as conn:
        existing = conn.execute("SELECT * FROM rules WHERE id = ?", (rule_id,)).fetchone()
        if existing is None:
            raise _not_found()
        merged = {
            "priority": body.priority if body.priority is not None else existing["priority"],
            "match_pattern": body.match_pattern if body.match_pattern is not None else existing["match_pattern"],
            "target_category": (
                body.target_category if body.target_category is not None else existing["target_category"]
            ),
            "target_subcategory": (
                body.target_subcategory if body.target_subcategory is not None else existing["target_subcategory"]
            ),
            "is_exclusion_rule": (
                body.is_exclusion_rule if body.is_exclusion_rule is not None else existing["is_exclusion_rule"]
            ),
            "exclusion_reason": (
                body.exclusion_reason if body.exclusion_reason is not None else existing["exclusion_reason"]
            ),
        }
        conn.execute(
            "UPDATE rules SET priority=?, match_pattern=?, target_category=?, target_subcategory=?, "
            "is_exclusion_rule=?, exclusion_reason=? WHERE id=?",
            (*merged.values(), rule_id),
        )
        row = conn.execute("SELECT * FROM rules WHERE id = ?", (rule_id,)).fetchone()
        return _row_to_out(row)


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))


@router.post("/reorder", response_model=list[RuleOut])
def reorder_rules(body: RuleReorderRequest):
    with get_conn() as conn:
        for priority, rule_id in enumerate(body.ordered_ids, start=1):
            conn.execute("UPDATE rules SET priority = ? WHERE id = ?", (priority, rule_id))
        rows = conn.execute("SELECT * FROM rules ORDER BY priority ASC").fetchall()
        return [_row_to_out(r) for r in rows]
