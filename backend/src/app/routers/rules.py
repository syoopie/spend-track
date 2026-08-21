from fastapi import APIRouter, HTTPException

from app import repo
from app.db import get_conn
from app.errors import api_error, not_found_error
from app.models import RuleCreateRequest, RuleOut, RuleReorderRequest, RuleUpdateRequest

router = APIRouter(prefix="/api/rules", tags=["rules"])


def _immutable() -> HTTPException:
    return api_error(403, "RULE_IMMUTABLE", "Default rules cannot be edited, deleted, or reordered.")


def _reorder_mismatch() -> HTTPException:
    return api_error(
        400,
        "REORDER_ID_MISMATCH",
        "ordered_ids must contain exactly every non-default rule id, no more and no less.",
    )


def _row_to_out(row) -> RuleOut:
    return RuleOut(
        id=row["id"],
        priority=row["priority"],
        match_pattern=row["match_pattern"],
        target_category=row["target_category"],
        target_subcategory=row["target_subcategory"],
        is_exclusion_rule=bool(row["is_exclusion_rule"]),
        exclusion_reason=row["exclusion_reason"],
        is_default=bool(row["is_default"]),
        display_label=row["display_label"],
    )


@router.get("", response_model=list[RuleOut])
def list_rules(include_default: bool = False):
    with get_conn() as conn:
        query = "SELECT * FROM rules" + ("" if include_default else " WHERE is_default = 0") + " ORDER BY priority ASC"
        rows = conn.execute(query).fetchall()
        return [_row_to_out(r) for r in rows]


@router.post("", response_model=RuleOut)
def create_rule(body: RuleCreateRequest):
    with get_conn() as conn:
        priority = body.priority if body.priority is not None else repo.next_user_rule_priority(conn)
        # target_category is NOT NULL per TECHNICAL_SPEC.md's schema even
        # though exclusion rules don't use it - default to "Others" for those.
        rule_id = repo.insert_rule(
            conn,
            priority=priority,
            match_pattern=body.match_pattern,
            target_category=body.target_category or "Others",
            target_subcategory=body.target_subcategory,
            is_exclusion_rule=body.is_exclusion_rule,
            exclusion_reason=body.exclusion_reason,
        )
        row = conn.execute("SELECT * FROM rules WHERE id = ?", (rule_id,)).fetchone()
        return _row_to_out(row)


@router.patch("/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: int, body: RuleUpdateRequest):
    with get_conn() as conn:
        existing = conn.execute("SELECT * FROM rules WHERE id = ?", (rule_id,)).fetchone()
        if existing is None:
            raise not_found_error("rule", "RULE_NOT_FOUND")
        if existing["is_default"]:
            raise _immutable()
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
        existing = conn.execute("SELECT is_default FROM rules WHERE id = ?", (rule_id,)).fetchone()
        if existing is not None and existing["is_default"]:
            raise _immutable()
        conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))


@router.post("/reorder", response_model=list[RuleOut])
def reorder_rules(body: RuleReorderRequest):
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT id FROM rules WHERE is_default = 1 AND id IN ({','.join('?' * len(body.ordered_ids))})",
            body.ordered_ids,
        ).fetchall() if body.ordered_ids else []
        if rows:
            raise _immutable()

        # Unknown ids silently no-op an UPDATE, and a partial list leaves the
        # omitted rules at their old priority - which can now numerically
        # collide with the freshly-assigned 1..N block below. Requiring an
        # exact match of the current editable set catches both.
        editable_ids = {r["id"] for r in conn.execute("SELECT id FROM rules WHERE is_default = 0").fetchall()}
        if len(body.ordered_ids) != len(editable_ids) or set(body.ordered_ids) != editable_ids:
            raise _reorder_mismatch()

        for priority, rule_id in enumerate(body.ordered_ids, start=1):
            conn.execute("UPDATE rules SET priority = ? WHERE id = ?", (priority, rule_id))
        rows = conn.execute("SELECT * FROM rules ORDER BY priority ASC").fetchall()
        return [_row_to_out(r) for r in rows]
