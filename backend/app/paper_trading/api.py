"""FastAPI routes for the paper-trading subsystem.

All routes are read-mostly except the explicit trade/report triggers; nothing
here touches broker execution or real money.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .engine import VirtualBroker
from .reports import portfolio_summary


class PlaceOrderRequest(BaseModel):
    agent_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1, max_length=12)
    quantity: float = Field(gt=0)
    side: str
    price: float | None = None
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    note: str | None = None


def register_paper_routes(app, broker: VirtualBroker) -> None:
    """Mount /api/paper/* routes (operator + admin roles, read-mostly)."""
    from fastapi import Depends, HTTPException

    from ..authorization import require_role

    # List of routes to add on the FastAPI app.

    @app.get("/api/paper/status", dependencies=[Depends(require_role("operator"))])
    def paper_status() -> dict:
        summary = portfolio_summary(broker.store)
        trader = getattr(app.state, "paper_trader", None)
        return {
            **summary,
            "platform_slug": broker.config.platform_slug,
            "initial_capital_per_agent": broker.config.initial_capital_per_agent,
            "total_virtual_capital": broker.config.total_virtual_capital,
            "enabled": bool(broker.config.enabled),
            "trading_loop_running": bool(trader and trader.is_running),
            "broker_execution": False,  # permanent boundary, verified below
        }

    @app.get("/api/paper/portfolios", dependencies=[Depends(require_role("operator"))])
    def paper_portfolios() -> dict:
        out = []
        for p in broker.all_portfolios():
            out.append({
                "agent_id": p.agent_id,
                "cash": round(p.cash, 2),
                "initial_capital": round(p.initial_capital, 2),
                "portfolio_value": round(p.portfolio_value, 2),
                "realized_pnl": round(p.realized_pnl, 2),
                "unrealized_pnl": round(p.unrealized_pnl, 2),
                "max_drawdown": round(p.max_drawdown, 4),
                "active": bool(p.active),
                "positions": [
                    {k: round(v, 4) if isinstance(v, float) else v for k, v in pos.items()}
                    for pos in p.positions
                ],
            })
        return {"count": len(out), "portfolios": out}

    @app.post("/api/paper/place_order", dependencies=[Depends(require_role("operator"))])
    def paper_place_order(payload: PlaceOrderRequest) -> dict:
        try:
            trade = broker.place_order(
                payload.agent_id, payload.symbol, payload.quantity, payload.side,
                payload.price,
                stop_loss_pct=payload.stop_loss_pct,
                take_profit_pct=payload.take_profit_pct,
                note=payload.note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True, "trade": trade, "broker_execution": False}

    @app.get("/api/paper/trades", dependencies=[Depends(require_role("operator"))])
    def paper_trades(agent_id: str, limit: int = 200) -> dict:
        return {"agent_id": agent_id, "trades": broker.store.trades(agent_id, limit=limit)}

    @app.get("/api/paper/snapshots", dependencies=[Depends(require_role("operator"))])
    def paper_snapshots(agent_id: str | None = None, limit: int = 30) -> dict:
        return {"snapshots": broker.store.snapshots(agent_id, limit=limit)}

    @app.get("/api/paper/trading-loop", dependencies=[Depends(require_role("operator"))])
    def paper_trading_loop_status() -> dict:
        trader = getattr(app.state, "paper_trader", None)
        return {
            "running": bool(trader and trader.is_running),
            "interval_seconds": trader.config.interval_seconds if trader else None,
            "last_executed_at": trader.last_executed_at if trader else None,
        }

    @app.get("/api/paper/rankings", dependencies=[Depends(require_role("operator"))])
    def paper_rankings(period_id: str | None = None) -> dict:
        from .reports import rank_agents

        period_id = period_id or "all"
        ranked = rank_agents(broker.store, period_id)
        return {"period_id": period_id, "rankings": ranked, "broker_execution": False}

    @app.post("/api/paper/snapshot", dependencies=[Depends(require_role("operator"))])
    def paper_snapshot_now(agent_id: str) -> dict:
        return broker.snapshot(agent_id)

    @app.get("/api/paper/backtest/run", dependencies=[Depends(require_role("operator"))])
    def paper_backtest_run(agent_id: str, symbol: str, strategy: str = "momentum_10",
                           interval: str = "15m") -> dict:
        from .backtest import run_paper_backtest

        result = run_paper_backtest(broker.store, agent_id, symbol, strategy,
                                    interval=interval)
        result["broker_execution"] = False
        return result

    @app.get("/api/paper/reports/daily", dependencies=[Depends(require_role("operator"))])
    def paper_daily_report(date: str | None = None) -> dict:
        from datetime import datetime, timezone
        from .reports import daily_report
        day = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return {"date": day, "agents": daily_report(broker.store, day)}

    @app.get("/api/paper/reports/monthly", dependencies=[Depends(require_role("operator"))])
    def paper_monthly_report(year: int | None = None, month: int | None = None) -> dict:
        from datetime import datetime, timezone
        from .reports import monthly_report
        now = datetime.now(timezone.utc)
        y = year or now.year
        m = month or now.month
        return {"period": f"{y:04d}-{m:02d}", "agents": monthly_report(broker.store, y, m)}

    @app.get("/api/paper/stats", dependencies=[Depends(require_role("operator"))])
    def paper_stats() -> dict:
        store = broker.store
        return {
            "registered_agents": store.count("paper_portfolios"),
            "initialized_portfolios": store.count("paper_portfolios"),
            "agents_with_open_positions": len(broker.agents_with_open_positions()),
            "trades_executed": store.count("paper_trades"),
        }
