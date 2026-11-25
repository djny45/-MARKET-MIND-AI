"""VirtualBroker — the core of the paper-trading engine.

Responsibilities:
  - initialize 550 independent portfolios, one per registered agent, each
    starting with $500 virtual capital (total $275,000, validated in config).
  - execute virtual orders with simulated fees/slippage and stop-loss /
    take-profit bookkeeping.
  - maintain per-agent P&L, drawdown, unrealized value so rankings and
    reports have real numbers to work from.

Everything here is virtual: it never touches broker execution or real money.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .config import VirtualCapitalConfig
from .store import PaperTradeStore


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class VirtualPortfolio:
    """Live view of one agent's paper portfolio."""
    agent_id: str
    cash: float
    initial_capital: float
    positions: list[dict] = field(default_factory=list)
    realized_pnl: float = 0.0
    max_drawdown: float = 0.0
    high_watermark: float = 0.0
    active: bool = False
    created_at: str = ""

    @property
    def portfolio_value(self) -> float:
        return self.cash + sum(p["quantity"] * p["current_price"] for p in self.positions)

    @property
    def drawdown_pct(self) -> float:
        if self.high_watermark <= 0:
            return 0.0
        return max(0.0, 1.0 - self.portfolio_value / self.high_watermark)

    @property
    def unrealized_pnl(self) -> float:
        return sum(p["quantity"] * (p["current_price"] - p["avg_entry"]) for p in self.positions)

    def pnl(self) -> float:
        return self.portfolio_value - self.initial_capital


class VirtualBroker:
    """Executes virtual orders for paper portfolios against a PaperTradeStore."""

    def __init__(self, config: VirtualCapitalConfig | None = None, store: PaperTradeStore | None = None):
        self.config = config or VirtualCapitalConfig.from_env()
        self.store = store or PaperTradeStore(self.config)
        self.store.init_schema()

    # -- initialization ---------------------------------------------------
    def initialize_all_portfolios(self, agent_ids: list[str] | None = None) -> int:
        """Create portfolios for every registered agent (idempotent, bulk)."""
        if agent_ids is None:
            agent_ids = [f"agent_{i:04d}" for i in range(1, self.config.registered_agents + 1)]
        with self.store._conn() as c:
            c.executemany(
                """INSERT OR IGNORE INTO paper_portfolios
                   (agent_id, initial_capital, current_cash, realized_pnl,
                    max_drawdown, high_watermark, created_at, status)
                   VALUES (?,?,?,0,0,?,datetime('now'),'initialized')""",
                [(a, self.config.initial_capital_per_agent, self.config.initial_capital_per_agent,
                  self.config.initial_capital_per_agent) for a in agent_ids],
            )
            c.execute(
                "UPDATE paper_portfolios SET high_watermark=initial_capital "
                "WHERE high_watermark<=0"
            )
        return len(self.store.portfolios())

    def _ensure_high_watermark(self, agent_id: str) -> None:
        pf = self.store.portfolio(agent_id)
        if pf and pf["high_watermark"] <= 0:
            self.store.update_portfolio(
                agent_id, high_watermark=max(pf["current_cash"], pf["initial_capital"]))

    # -- views --------------------------------------------------------------
    def portfolio(self, agent_id: str) -> VirtualPortfolio | None:
        pf = self.store.portfolio(agent_id)
        if not pf:
            return None
        return VirtualPortfolio(
            agent_id=agent_id,
            cash=pf["current_cash"],
            initial_capital=pf["initial_capital"],
            positions=[dict(p) for p in self.store.positions(agent_id)],
            realized_pnl=pf["realized_pnl"],
            max_drawdown=pf["max_drawdown"],
            high_watermark=pf["high_watermark"],
            active=bool(self.store.positions(agent_id)),
            created_at=pf["created_at"],
        )

    def all_portfolios(self) -> list[VirtualPortfolio]:
        """All 550 portfolios with positions in 3 queries (no N+1)."""
        rows = self.store.portfolios()
        positions = self.store._conn().execute(
            "SELECT * FROM paper_positions ORDER BY agent_id, symbol"
        ).fetchall()
        by_agent: dict[str, list[dict]] = {}
        for row in positions:
            by_agent.setdefault(row["agent_id"], []).append(dict(row))
        out = []
        for pf in rows:
            pos = by_agent.get(pf["agent_id"], [])
            out.append(VirtualPortfolio(
                agent_id=pf["agent_id"],
                cash=pf["current_cash"],
                initial_capital=pf["initial_capital"],
                positions=pos,
                realized_pnl=pf["realized_pnl"],
                max_drawdown=pf["max_drawdown"],
                high_watermark=pf["high_watermark"],
                active=bool(pos),
                created_at=pf["created_at"],
            ))
        return out

    def agents_with_open_positions(self) -> list[str]:
        return sorted(set(self.store.active_agents()))

    # -- order execution -----------------------------------------------------
    def place_order(
        self,
        agent_id: str,
        symbol: str,
        quantity: float,
        side: str,
        price: float | None = None,
        *,
        stop_loss_pct: float | None = None,
        take_profit_pct: float | None = None,
        note: str | None = None,
        **_ignored,
    ) -> dict:
        """Execute a virtual BUY/SELL at `price` (defaults to 1.0 reference).

        Fees and slippage are simulated as a small percentage of notional.
        Returns the executed trade record.
        """
        side = side.upper()
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        pf = self.store.portfolio(agent_id)
        if not pf:
            raise ValueError(f"no portfolio for agent {agent_id}")
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        ref_price = float(price) if price else 1.0
        notional = quantity * ref_price
        fee = notional * self.config.commission_bps / 10000.0
        slip = notional * self.config.slippage_bps / 10000.0
        exec_price = ref_price * (1.0 + (fee + slip) / notional) if side == "BUY" else ref_price * (1.0 - (fee + slip) / notional)

        pos = self.store.get_position(agent_id, symbol)
        pnl = 0.0
        cash_delta = -notional
        if side == "BUY":
            if pf["current_cash"] - notional - fee - slip < -1e-9:
                raise ValueError(f"insufficient cash for {agent_id}")
            slp = stop_loss_pct if stop_loss_pct is not None else (pos.get("stop_loss_pct") if pos else None)
            tpp = take_profit_pct if take_profit_pct is not None else (pos.get("take_profit_pct") if pos else None)
            if pos:
                q = pos["quantity"] + quantity
                avg = ((pos["quantity"] * pos["avg_entry"]) + notional) / q
                self.store.set_position(agent_id, symbol, quantity=q, avg_entry=avg, current_price=exec_price,
                                        stop_loss_pct=slp, take_profit_pct=tpp, updated_at=_utcnow())
            else:
                self.store.set_position(agent_id, symbol, quantity=quantity, avg_entry=exec_price,
                                        current_price=exec_price, stop_loss_pct=slp, take_profit_pct=tpp,
                                        updated_at=_utcnow())
            cash_delta -= fee + slip
        else:  # SELL
            if not pos or pos["quantity"] < quantity - 1e-9:
                raise ValueError(f"insufficient position for {agent_id}/{symbol}")
            pnl = (exec_price - pos["avg_entry"]) * quantity
            remaining = pos["quantity"] - quantity
            if remaining <= 1e-9:
                self.store.remove_position(agent_id, symbol)
            else:
                self.store.set_position(agent_id, symbol, quantity=remaining, avg_entry=pos["avg_entry"],
                                        current_price=exec_price, updated_at=_utcnow())
            cash_delta += notional - fee - slip
            self.store.update_portfolio(agent_id, realized_pnl=pf["realized_pnl"] + pnl)
        new_cash = pf["current_cash"] + cash_delta
        self.store.update_portfolio(agent_id, current_cash=new_cash)
        trade_id = self.store.append_trade(
            agent_id, symbol, side, quantity, exec_price, fee, slip, pnl, side == "SELL", _utcnow())
        self._refresh_metrics(agent_id)
        return {
            "trade_id": trade_id, "agent_id": agent_id, "symbol": symbol, "side": side,
            "quantity": quantity, "reference_price": ref_price, "execution_price": round(exec_price, 8),
            "fee": round(fee, 8), "slippage": round(slip, 8), "pnl": round(pnl, 8),
            "mode": "virtual", "note": note, "executed_at": _utcnow(),
        }

    # -- stop-loss / take-profit --------------------------------------------------
    def check_stop_loss_take_profit(self, agent_id: str, symbol: str,
                                    current_price: float | None = None) -> list[dict]:
        """Close a position if stop-loss or take-profit triggers."""
        pos = self.store.get_position(agent_id, symbol)
        if not pos or not pos["quantity"]:
            return []
        price = float(current_price) if current_price else 1.0
        if pos.get("stop_loss_pct") and price <= pos["avg_entry"] * (1 - pos["stop_loss_pct"] / 100):
            return [self.place_order(agent_id, symbol, pos["quantity"], "SELL", note="stop_loss_hit")]
        if pos.get("take_profit_pct") and price >= pos["avg_entry"] * (1 + pos["take_profit_pct"] / 100):
            return [self.place_order(agent_id, symbol, pos["quantity"], "SELL", note="take_profit_hit")]
        return []

    # -- metrics -------------------------------------------------------------------
    def _refresh_metrics(self, agent_id: str) -> None:
        pf = self.portfolio(agent_id)
        if not pf:
            return
        hw = max(pf.high_watermark, pf.portfolio_value)
        dd = max(0.0, 1.0 - pf.portfolio_value / hw) if hw > 0 else 0.0
        self.store.update_portfolio(agent_id, high_watermark=hw,
                                    max_drawdown=max(pf.max_drawdown, dd))

    def refresh_all_metrics(self) -> int:
        """Bulk high-watermark/drawdown refresh in one SQL statement.

        Avoids 550 per-agent reads/writes (which dominated tick latency on
        network filesystems) while computing exactly the same metrics.
        """
        with self.store._conn() as c:
            cur = c.execute("""
                UPDATE paper_portfolios
                SET high_watermark = MAX(high_watermark, mark_to_market),
                    max_drawdown = MAX(max_drawdown, drawdown)
                FROM (
                    SELECT p.agent_id,
                           p.current_cash + COALESCE((
                               SELECT SUM(quantity * current_price)
                               FROM paper_positions ps
                               WHERE ps.agent_id = p.agent_id), 0) AS mark_to_market,
                           MAX(0.0, 1.0 - (p.current_cash + COALESCE((
                               SELECT SUM(quantity * current_price)
                               FROM paper_positions ps2
                               WHERE ps2.agent_id = p.agent_id), 0))
                               / NULLIF(MAX(p.high_watermark,
                                   p.current_cash + COALESCE((
                                     SELECT SUM(quantity * current_price)
                                     FROM paper_positions ps3
                                     WHERE ps3.agent_id = p.agent_id), 0)), 0)) AS drawdown
                    FROM paper_portfolios p
                ) m
                WHERE m.agent_id = paper_portfolios.agent_id
            """)
            return cur.rowcount

    def snapshot(self, agent_id: str, snapshot_date: str | None = None) -> dict:
        pf = self.portfolio(agent_id)
        if not pf:
            raise ValueError(f"no portfolio for {agent_id}")
        snap_date = snapshot_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.store.insert_snapshot(agent_id, snap_date, pf.portfolio_value, pf.pnl(), pf.drawdown_pct)
        return {"agent_id": agent_id, "date": snap_date, "portfolio_value": round(pf.portfolio_value, 2),
                "pnl": round(pf.pnl(), 2), "drawdown_pct": round(pf.drawdown_pct, 4)}
