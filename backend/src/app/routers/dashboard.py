import calendar
import sqlite3
from collections import defaultdict
from datetime import date

from fastapi import APIRouter

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


def _fetch_month_transactions(
    conn: sqlite3.Connection, month: str, account_id: str | None
) -> list[sqlite3.Row]:
    clauses = ["transaction_date LIKE ?", "is_excluded = 0"]
    params: list = [f"{month}%"]
    if account_id:
        clauses.append("account_id = ?")
        params.append(account_id)
    where = " AND ".join(clauses)
    return conn.execute(f"SELECT * FROM transactions WHERE {where}", params).fetchall()


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


def _daily_cumulative_outflow(conn: sqlite3.Connection, month: str, account_id: str | None) -> list[float]:
    txs = _fetch_month_transactions(conn, month, account_id)
    days_in_month = calendar.monthrange(int(month[:4]), int(month[5:7]))[1]
    daily = [0.0] * (days_in_month + 1)  # 1-indexed by day
    for t in txs:
        if t["amount"] < 0:
            day = int(t["transaction_date"][8:10])
            daily[day] += -t["amount"]
    cumulative = []
    running = 0.0
    for day in range(1, days_in_month + 1):
        running += daily[day]
        cumulative.append(round(running, 2))
    return cumulative


def _spend_velocity(current: list[float], previous: list[float]) -> list[VelocityPoint]:
    n = max(len(current), len(previous))
    points = []
    for i in range(n):
        cur = current[i] if i < len(current) else (current[-1] if current else 0.0)
        prev = previous[i] if i < len(previous) else (previous[-1] if previous else 0.0)
        points.append(VelocityPoint(day=i + 1, current_month_cumulative=cur, previous_month_cumulative=prev))
    return points


def _top_entries(txs: list[sqlite3.Row], contact_names: dict[int, str], *, paynow: bool, limit: int = 5) -> list[TopEntry]:
    totals: dict[str, float] = defaultdict(float)
    for t in txs:
        if t["amount"] >= 0:
            continue
        is_paynow_tx = t["category"] == "PayNow Transfers"
        if is_paynow_tx != paynow:
            continue
        if is_paynow_tx and t["contact_id"] is not None:
            name = contact_names.get(t["contact_id"], normalize_merchant(t["raw_description"]).title())
        else:
            name = normalize_merchant(t["raw_description"]).title() or t["raw_description"]
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

        cash_flow = []
        for m in _months_between(date_from, date_to):
            m_txs = _fetch_month_transactions(conn, m, account_id)
            inflow = sum(t["amount"] for t in m_txs if t["amount"] > 0)
            outflow = sum(-t["amount"] for t in m_txs if t["amount"] < 0)
            cash_flow.append(CashFlowMonth(month=m, inflow=round(inflow, 2), outflow=round(outflow, 2)))

        is_single_month = date_from == date_to
        spend_velocity: list[VelocityPoint] = []
        if is_single_month:
            current_cum = _daily_cumulative_outflow(conn, date_from, account_id)
            previous_cum = _daily_cumulative_outflow(conn, _shift_month(date_from, -1), account_id)
            spend_velocity = _spend_velocity(current_cum, previous_cum)

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
