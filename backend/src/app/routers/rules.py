from fastapi import APIRouter, HTTPException

from app import rule_catalog
from app.db import get_conn
from app.errors import api_error, not_found_error
from app.models import MatchCountOut, RuleCreateRequest, RuleOut, RuleReorderRequest, RuleUpdateRequest

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
        direction=row["direction"],
        is_default=bool(row["is_default"]),
        display_label=row["display_label"],
    )


@router.get("", response_model=list[RuleOut])
def list_rules(include_default: bool = False):
    with get_conn() as conn:
        query = "SELECT * FROM rules" + ("" if include_default else " WHERE is_default = 0") + " ORDER BY priority ASC"
        rows = conn.execute(query).fetchall()
        return [_row_to_out(r) for r in rows]


@router.get("/match-count", response_model=MatchCountOut)
def match_count(pattern: str):
    # Backs the review dialog's "matches N transactions in history" live
    # count (REV-5 in UI Review.dc.html) - lets a user see, before creating
    # a rule, whether the pattern they typed is a reusable merchant keyword
    # or something so specific (the full raw bank description, say) it'll
    # only ever match the one transaction it was copied from. Same
    # case-insensitive substring match as engine/rules.py::categorize's
    # own `rule["match_pattern"].upper() in desc_upper` check, so this
    # count is never optimistic about what a real rule would actually
    # match going forward.
    pattern = pattern.strip()
    if not pattern:
        return MatchCountOut(count=0)
    # Escape LIKE's own wildcard characters so a pattern that happens to
    # contain a literal % or _ (rare, but bank descriptions do sometimes
    # include promo text like "50% OFF") is matched literally, not as a
    # wildcard.
    escaped = pattern.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM transactions WHERE UPPER(raw_description) LIKE '%' || UPPER(?) || '%' ESCAPE '\\'",
            (escaped,),
        ).fetchone()
        return MatchCountOut(count=row["n"])


@router.post("", response_model=RuleOut)
def create_rule(body: RuleCreateRequest):
    with get_conn() as conn:
        priority = body.priority if body.priority is not None else rule_catalog.next_user_rule_priority(conn)
        # target_category is NOT NULL per docs/technical-spec.md's schema even
        # though exclusion rules don't use it - default to "Others" for those.
        target_category = body.target_category or "Others"
        # A category-assigning rule's direction always matches its own
        # category (there's no meaningful scenario where they'd differ - see
        # rule_catalog.category_direction's docstring), so it's derived rather than
        # independently trusted from the request unless the caller is an
        # exclusion rule, which has no category to derive it from.
        direction = body.direction or rule_catalog.category_direction(conn, target_category)
        rule_id = rule_catalog.insert_rule(
            conn,
            priority=priority,
            match_pattern=body.match_pattern,
            target_category=target_category,
            target_subcategory=body.target_subcategory,
            is_exclusion_rule=body.is_exclusion_rule,
            exclusion_reason=body.exclusion_reason,
            direction=direction,
            display_label=None if body.is_exclusion_rule else body.display_label,
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
        # An explicit direction always wins. Otherwise, a category-assigning
        # rule re-derives it from whatever category it now ends up
        # targeting (so switching a rule's category can't leave a stale,
        # mismatched direction behind) - an exclusion rule has no category
        # to derive from, so it just keeps whatever it already had.
        if body.direction is not None:
            merged["direction"] = body.direction
        elif not merged["is_exclusion_rule"]:
            merged["direction"] = rule_catalog.category_direction(
                conn, merged["target_category"], default=existing["direction"]
            )
        else:
            merged["direction"] = existing["direction"]
        # Added last so dict insertion order matches the UPDATE's column
        # order below (this function binds params via *merged.values()).
        merged["display_label"] = (
            body.display_label if body.display_label is not None else existing["display_label"]
        )
        if merged["is_exclusion_rule"]:
            merged["display_label"] = None  # meaningless for an exclusion rule - see create_rule's same rule
        conn.execute(
            "UPDATE rules SET priority=?, match_pattern=?, target_category=?, target_subcategory=?, "
            "is_exclusion_rule=?, exclusion_reason=?, direction=?, display_label=? WHERE id=?",
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
