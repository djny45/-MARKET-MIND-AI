"""Daily and monthly performance reports + strategy rankings for paper trading.

Everything is computed from the persistent paper_trades / paper_snapshots /
paper_rankings tables via PaperTradeStore; nothing is invented or claimed.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta

from .store import PaperTradeStore


def _fmt(v: float, nd=4) -> float:
    return round(v, nd)


def daily_report(store: PaperTradeStore, snapshot_date: str) -> list[dict]:
    """Net P&L, realized P&L, trade count and gross exposure per agent for a date."""
    rows = [t for t in store.trades(limit=100000) if t["executed_at"][:10] == snapshot_date]
    # `trades()` returns newest-first; order doesn't matter for totals.
    by_agent: dict[str, dict] = defaultdict(lambda: {"realized_pnl": 0.0, "gross_volume": 0.0, "trade_count": 0, "buy_volume": 0.0})
    for t in rows:
        a = by_agent[t["agent_id"]]
        a["trade_count"] += 1
        a["gross_volume"] += abs(t["quantity"] * t["price"])
        if t["side"] == "BUY":
            a["buy_volume"] += abs(t["quantity"] * t["price"])
        if t["realized"]:
            a["realized_pnl"] += t["pnl"]
    out = []
    for agent_id in sorted(by_agent):
        a = by_agent[agent_id]
        pf = store.portfolio(agent_id)
        out.append({
            "agent_id": agent_id,
            "date": snapshot_date,
            "realized_pnl": _fmt(a["realized_pnl"]),
            "trade_count": a["trade_count"],
            "gross_volume": _fmt(a["gross_volume"]),
            "net_pnl": _fmt((pf["realized_pnl"] if pf else a["realized_pnl"])),
        })
    return sorted(out, key=lambda r: r["realized_pnl"], reverse=True)


def monthly_report(store: PaperTradeStore, year: int, month: int) -> list[dict]:
    """Aggregated per-agent monthly performance (P&L, return, trade count)."""
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    trades = store.trades(limit=100000)
    window = [t for t in trades if start.isoformat() <= t["executed_at"][:10] < end.isoformat()]
    by_agent: dict[str, dict] = defaultdict(lambda: {"realized_pnl": 0.0, "trade_count": 0, "gross_volume": 0.0})
    for t in window:
        a = by_agent[t["agent_id"]]
        a["trade_count"] += 1
        a["gross_volume"] += abs(t["quantity"] * t["price"])
        if t["realized"]:
            a["realized_pnl"] += t["pnl"]
    out = []
    for agent_id in sorted(by_agent):
        a = by_agent[agent_id]
        out.append({
            "agent_id": agent_id,
            "period": f"{year:04d}-{month:02d}",
            "realized_pnl": _fmt(a["realized_pnl"]),
            "trade_count": a["trade_count"],
            "gross_volume": _fmt(a["gross_volume"]),
        })
    return sorted(out, key=lambda r: r["realized_pnl"], reverse=True)


def rank_agents(store: PaperTradeStore, period_id: str, agent_ids: list[str] | None = None) -> list[dict]:
    """Rank agents by realized P&L for a period; writes paper_rankings rows."""
    rows = store.rankings(period_id)
    if rows:
        return rows
    ranked = sorted(store.portfolios(), key=lambda p: (p["realized_pnl"], p["agent_id"]), reverse=False)
    ranked = [p for p in ranked if (agent_ids is None or p["agent_id"] in agent_ids)]
    out = []
    for rank, p in enumerate(ranked, start=1):
        pct = (p["realized_pnl"] / p["initial_capital"] * 100.0) if p["initial_capital"] else 0.0
        out.append({
            "period_id": period_id, "rank": rank, "agent_id": p["agent_id"],
            "realized_pnl": _fmt(p["realized_pnl"]),
            "pnl_pct_of_capital": _fmt(pct),
            "max_drawdown": _fmt(p["max_drawdown"]),
        })
        try:
            from datetime import datetime, timezone
            store.upsert_ranking(period_id, p["agent_id"], period_id, period_id, p["realized_pnl"])
        except Exception:
            pass
    return out


def portfolio_summary(store: PaperTradeStore) -> dict:
    """Aggregate paper system summary used by the health/status endpoint.

    Uses a bounded number of SQL queries (no N+1 per agent), so health probes
    stay fast even with 550 portfolios.
    """
    portfolios = store.portfolios()
    positions = store.active_agents()
    # Market value = cash + sum(open qty * last price), one query.
    with store._conn() as c:
        mark_to_market = c.execute(
            "SELECT COALESCE(SUM(quantity * current_price), 0) FROM paper_positions"
        ).fetchone()[0]
    total_value = sum(p["current_cash"] for p in portfolios) + (mark_to_market or 0.0)
    return {
        "registered_agents": len(portfolios),
        "initialized_portfolios": len(portfolios),
        "agents_with_open_positions": len(positions),
        "total_virtual_capital": _fmt(sum(p["initial_capital"] for p in portfolios)),
        "total_portfolio_value": _fmt(total_value),
        "active_agents": len(positions),
    }
