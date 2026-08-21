import calendar
import re
import sqlite3
from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException

from app.db import get_conn
from app.engine.refunds import normalize_merchant
from app.models import (
    CashFlowMonth,
    CategoryBreakdownSlice,
    DashboardSummaryOut,
    MetricCards,
    MonthlyTotal,
    TopEntry,
    VelocityPoint,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

_MONTH_KEY_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _validate_month_key(value: str, param_name: str) -> None:
    """date_from/date_to are month keys ("YYYY-MM"), not full dates. Every
    downstream helper (_shift_month's int() split, date.fromisoformat with a
    day appended) assumes this shape and raises an unhandled ValueError -> 500
    on anything else, so reject bad input here with a clean 422 instead."""
    if not _MONTH_KEY_RE.match(value):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_MONTH_FORMAT",
                "message": f"{param_name} must be in YYYY-MM format, got {value!r}.",
            },
        )


def _shift_month(month: str, delta: int) -> str:
    y, m = (int(p) for p in month.split("-"))
    idx = y * 12 + (m - 1) + delta
    y2, m2 = divmod(idx, 12)
    return f"{y2:04d}-{m2 + 1:02d}"


def _months_between(date_from: str, date_to: str) -> list[str]:
    months = []
    m = date_from
    while m <= date_to:
        months.append(m)
        m = _shift_month(m, 1)
    return months


def _fetch_range_transactions(
    conn: sqlite3.Connection, date_from: str, date_to: str, account_id: str | None
) -> list[sqlite3.Row]:
    clauses = ["transaction_date >= ?", "transaction_date <= ?", "is_excluded = 0"]
    params: list = [f"{date_from}-01", f"{date_to}-31"]
    if account_id:
        clauses.append("account_id = ?")
        params.append(account_id)
    where = " AND ".join(clauses)
    return conn.execute(f"SELECT * FROM transactions WHERE {where}", params).fetchall()


def _latest_month(conn: sqlite3.Connection, account_id: str | None) -> str:
    clause = " WHERE account_id = ?" if account_id else ""
    params = [account_id] if account_id else []
    row = conn.execute(f"SELECT MAX(transaction_date) FROM transactions{clause}", params).fetchone()
    latest = row[0]
    return latest[:7] if latest else date.today().isoformat()[:7]


def _metrics(txs: list[sqlite3.Row]) -> MetricCards:
    inflow = sum(t["amount"] for t in txs if t["amount"] > 0)
    outflow = sum(-t["amount"] for t in txs if t["amount"] < 0)
    return MetricCards(
        net_expenditure=round(inflow - outflow, 2),
        total_inflow=round(inflow, 2),
        total_outflow=round(outflow, 2),
    )


def _category_breakdown(txs: list[sqlite3.Row]) -> list[CategoryBreakdownSlice]:
    totals: dict[str, float] = defaultdict(float)
    for t in txs:
        if t["amount"] < 0:
            totals[t["category"]] += -t["amount"]
    outflow = sum(totals.values())
    return [
        CategoryBreakdownSlice(
            category=cat, amount=round(amt, 2), pct=round(amt / outflow * 100, 1) if outflow else 0.0
        )
        for cat, amt in sorted(totals.items(), key=lambda kv: -kv[1])
    ]


def _period_daily_cumulative_outflow(
    conn: sqlite3.Connection, date_from: str, date_to: str, account_id: str | None
) -> list[float]:
    """date_from/date_to are month keys (YYYY-MM) - walks every calendar day
    across all months in the range so this works for a single month or a
    many-month range alike."""
    last_day = calendar.monthrange(int(date_to[:4]), int(date_to[5:7]))[1]
    start = date.fromisoformat(f"{date_from}-01")
    end = date.fromisoformat(f"{date_to}-{last_day:02d}")

    clauses = ["transaction_date >= ?", "transaction_date <= ?", "is_excluded = 0"]
    params: list = [start.isoformat(), end.isoformat()]
    if account_id:
        clauses.append("account_id = ?")
        params.append(account_id)
    where = " AND ".join(clauses)
    rows = conn.execute(f"SELECT transaction_date, amount FROM transactions WHERE {where}", params).fetchall()

    daily: dict[str, float] = defaultdict(float)
    for r in rows:
        if r["amount"] < 0:
            daily[r["transaction_date"]] += -r["amount"]

    cumulative = []
    running = 0.0
    d = start
    while d <= end:
        running += daily.get(d.isoformat(), 0.0)
        cumulative.append(round(running, 2))
        d += timedelta(days=1)
    return cumulative


def _spend_velocity(current: list[float], previous: list[float], period_start: date) -> list[VelocityPoint]:
    n = max(len(current), len(previous))
    points = []
    for i in range(n):
        cur = current[i] if i < len(current) else (current[-1] if current else 0.0)
        prev = previous[i] if i < len(previous) else (previous[-1] if previous else 0.0)
        points.append(
            VelocityPoint(
                day=i + 1,
                date=(period_start + timedelta(days=i)).isoformat(),
                current_period_cumulative=cur,
                previous_period_cumulative=prev,
            )
        )
    return points


_PAYNOW_LABEL_PREFIXES = ("PayNow to ", "PayNow from ")


def _strip_paynow_prefix(label: str | None) -> str | None:
    if label:
        for prefix in _PAYNOW_LABEL_PREFIXES:
            if label.startswith(prefix):
                return label[len(prefix):]
    return label


def _top_entries(txs: list[sqlite3.Row], contact_names: dict[int, str], *, paynow: bool, limit: int = 5) -> list[TopEntry]:
    totals: dict[str, float] = defaultdict(float)
    for t in txs:
        if t["amount"] >= 0:
            continue
        is_paynow_tx = t["category"] == "Paynow"
        if is_paynow_tx != paynow:
            continue
        if is_paynow_tx:
            # matched_label is already "PayNow to {name}" (see engine/rules.py)
            # - the contact's own name wins when we have one, otherwise fall
            # back to whatever name was extracted from the raw description.
            name = (
                contact_names.get(t["contact_id"])
                if t["contact_id"] is not None
                else None
            ) or _strip_paynow_prefix(t["matched_label"]) or normalize_merchant(t["raw_description"]).title()
        else:
            name = t["matched_label"] or normalize_merchant(t["raw_description"]).title() or t["raw_description"]
        totals[name] += -t["amount"]
    ranked = sorted(totals.items(), key=lambda kv: -kv[1])[:limit]
    return [TopEntry(name=name, amount=round(amt, 2)) for name, amt in ranked]


@router.get("/monthly-totals", response_model=list[MonthlyTotal])
def get_monthly_totals(account_id: str | None = None):
    """Per-month inflow/outflow for every month with at least one transaction -
    powers the month-range calendar picker so each cell can show its totals."""
    with get_conn() as conn:
        clauses = ["is_excluded = 0"]
        params: list = []
        if account_id:
            clauses.append("account_id = ?")
            params.append(account_id)
        where = " AND ".join(clauses)
        rows = conn.execute(
            f"SELECT transaction_date, amount FROM transactions WHERE {where}", params
        ).fetchall()

        totals: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])  # [inflow, outflow]
        for r in rows:
            month = r["transaction_date"][:7]
            if r["amount"] > 0:
                totals[month][0] += r["amount"]
            else:
                totals[month][1] += -r["amount"]

        return [
            MonthlyTotal(month=month, inflow=round(inflow, 2), outflow=round(outflow, 2))
            for month, (inflow, outflow) in sorted(totals.items())
        ]


@router.get("/summary", response_model=DashboardSummaryOut)
def get_dashboard_summary(date_from: str | None = None, date_to: str | None = None, account_id: str | None = None):
    if date_from:
        _validate_month_key(date_from, "date_from")
    if date_to:
        _validate_month_key(date_to, "date_to")

    with get_conn() as conn:
        if not date_from and not date_to:
            date_from = date_to = _latest_month(conn, account_id)
        elif not date_to:
            date_to = date_from
        elif not date_from:
            date_from = date_to
        if date_from > date_to:
            date_from, date_to = date_to, date_from

        txs = _fetch_range_transactions(conn, date_from, date_to, account_id)

        months_in_range = _months_between(date_from, date_to)
        # Bucketed from the txs already fetched above, rather than a separate
        # query per month (was an N+1 for wide ranges).
        month_totals: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
        for t in txs:
            bucket = month_totals[t["transaction_date"][:7]]
            if t["amount"] > 0:
                bucket[0] += t["amount"]
            else:
                bucket[1] += -t["amount"]
        cash_flow = [
            CashFlowMonth(month=m, inflow=round(month_totals[m][0], 2), outflow=round(month_totals[m][1], 2))
            for m in months_in_range
        ]

        months_count = len(months_in_range)
        prev_date_from = _shift_month(date_from, -months_count)
        prev_date_to = _shift_month(date_to, -months_count)
        current_cum = _period_daily_cumulative_outflow(conn, date_from, date_to, account_id)
        previous_cum = _period_daily_cumulative_outflow(conn, prev_date_from, prev_date_to, account_id)
        spend_velocity = _spend_velocity(current_cum, previous_cum, date.fromisoformat(f"{date_from}-01"))

        contact_rows = conn.execute("SELECT id, name FROM contacts").fetchall()
        contact_names = {r["id"]: r["name"] for r in contact_rows}

        return DashboardSummaryOut(
            date_from=date_from,
            date_to=date_to,
            metrics=_metrics(txs),
            cash_flow=cash_flow,
            category_breakdown=_category_breakdown(txs),
            spend_velocity=spend_velocity,
            top_merchants=_top_entries(txs, contact_names, paynow=False),
            top_paynow_contacts=_top_entries(txs, contact_names, paynow=True),
        )
