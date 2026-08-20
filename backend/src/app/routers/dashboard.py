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
    TopEntry,
    VelocityPoint,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _shift_month(month: str, delta: int) -> str:
    y, m = (int(p) for p in month.split("-"))
    idx = y * 12 + (m - 1) + delta
    y2, m2 = divmod(idx, 12)
    return f"{y2:04d}-{m2 + 1:02d}"


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


def _latest_month(conn: sqlite3.Connection, account_id: str | None) -> str:
    clause = " WHERE account_id = ?" if account_id else ""
    params = [account_id] if account_id else []
    row = conn.execute(f"SELECT MAX(transaction_date) FROM transactions{clause}", params).fetchone()
    latest = row[0]
    return latest[:7] if latest else date.today().isoformat()[:7]


def _metrics(txs: list[sqlite3.Row]) -> MetricCards:
    inflow = sum(t["amount"] for t in txs if t["amount"] > 0)
    outflow = sum(-t["amount"] for t in txs if t["amount"] < 0)
    paynow_total = sum(-t["amount"] for t in txs if t["amount"] < 0 and t["category"] == "PayNow Transfers")
    card_total = outflow - paynow_total
    paynow_pct = round(paynow_total / outflow * 100, 1) if outflow else 0.0
    card_pct = round(100 - paynow_pct, 1) if outflow else 0.0
    return MetricCards(
        net_expenditure=round(inflow - outflow, 2),
        total_inflow=round(inflow, 2),
        total_outflow=round(outflow, 2),
        paynow_total=round(paynow_total, 2),
        card_total=round(card_total, 2),
        paynow_pct=paynow_pct,
        card_pct=card_pct,
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


@router.get("/summary", response_model=DashboardSummaryOut)
def get_dashboard_summary(month: str | None = None, account_id: str | None = None):
    with get_conn() as conn:
        month = month or _latest_month(conn, account_id)
        prev_month = _shift_month(month, -1)

        txs = _fetch_month_transactions(conn, month, account_id)

        cash_flow = []
        for i in range(5, -1, -1):
            m = _shift_month(month, -i)
            m_txs = _fetch_month_transactions(conn, m, account_id)
            inflow = sum(t["amount"] for t in m_txs if t["amount"] > 0)
            outflow = sum(-t["amount"] for t in m_txs if t["amount"] < 0)
            cash_flow.append(CashFlowMonth(month=m, inflow=round(inflow, 2), outflow=round(outflow, 2)))

        current_cum = _daily_cumulative_outflow(conn, month, account_id)
        previous_cum = _daily_cumulative_outflow(conn, prev_month, account_id)

        contact_rows = conn.execute("SELECT id, name FROM contacts").fetchall()
        contact_names = {r["id"]: r["name"] for r in contact_rows}

        return DashboardSummaryOut(
            month=month,
            metrics=_metrics(txs),
            cash_flow=cash_flow,
            category_breakdown=_category_breakdown(txs),
            spend_velocity=_spend_velocity(current_cum, previous_cum),
            top_merchants=_top_entries(txs, contact_names, paynow=False),
            top_paynow_contacts=_top_entries(txs, contact_names, paynow=True),
        )
