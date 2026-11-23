"""Shadow-order session engine and daily simulated risk reports.

Every order recorded here is a log-only hypothesis about a paper trade:
``executed`` is always False and ``mode`` is always ``shadow_log_only``. There is
no broker connection, no credential use and no execution path.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .audit_jsonl import append_record, read_records
from .research_backtest_harness import BacktestConfig

LOG_PATH = Path(os.getenv("MARKET_MIND_DB", "./data/market_mind.db")).with_name(
    "research_shadow_log.jsonl"
)


def _metrics_from_returns(returns: list[float]) -> dict[str, float]:
    if not returns:
        return {"daily_pnl": 0.0, "net_pnl": 0.0, "gross_pnl": 0.0, "trades": 0,
                "sharpe": 0.0, "sortino": 0.0, "max_drawdown": 0.0}
    equity = [1.0]
    for value in returns:
        equity.append(equity[-1] * (1 + value))
    peak = equity[0]
    drawdown = 0.0
    for value in equity:
        peak = max(peak, value)
        drawdown = min(drawdown, value / peak - 1)
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / len(returns)
    std = math.sqrt(variance)
    downside = [r for r in returns if r < 0]
    down_dev = math.sqrt(sum(r * r for r in downside) / len(returns)) if downside else 0.0
    return {
        "gross_pnl": sum(returns),
        "net_pnl": sum(returns),
        "daily_pnl": mean,
        "trades": len(returns),
        "sharpe": (mean / std * math.sqrt(252)) if std else 0.0,
        "sortino": (mean / down_dev * math.sqrt(252)) if down_dev else 0.0,
        "max_drawdown": drawdown,
    }


@dataclass
class ShadowOrder:
    id: int
    run_id: str
    symbol: str
    side: str
    quantity: float
    reference_price: float
    notional: float
    cost: float
    expected_pnl: float
    rationale: str
    timestamp: str
    order_type: str = "model_order"

    def as_record(self) -> dict:
        record = asdict(self)
        record.update({
            "executed": False,
            "mode": "shadow_log_only",
            "research_only": True,
            "broker_execution": False,
        })
        return record


class ShadowSessionEngine:
    """Deterministic log-only order and daily-report engine."""

    def __init__(self, config: BacktestConfig, log_path: Path | None = None):
        config.validate()
        self.config = config
        self.log_path = Path(log_path) if log_path else LOG_PATH
        self._orders: list[ShadowOrder] = []
        self._run_id = ""
        self._next_id = 0

    def begin_run(self, run_id: str) -> str:
        if not run_id or not isinstance(run_id, str):
            raise ValueError("run_id is required")
        self._run_id = run_id
        self._orders = []
        self._next_id = 0
        return run_id

    def record_shadow_order(self, order: dict, *, run_id: str) -> ShadowOrder:
        """Record one shadow order and persist it to the append-only audit log."""
        if self._run_id != run_id:
            self._run_id = run_id
            self._next_id = 0
        for field_name in ("symbol", "side", "quantity", "reference_price", "timestamp"):
            if field_name not in order:
                raise ValueError(f"shadow order missing required field: {field_name}")
        if order["quantity"] < 0:
            raise ValueError("shadow order quantity cannot be negative")
        if order["side"] not in {"BUY", "SELL"}:
            raise ValueError("shadow order side must be BUY or SELL")
        shadow = ShadowOrder(
            id=self._next_id,
            run_id=run_id,
            symbol=order["symbol"],
            side=order["side"],
            quantity=float(order["quantity"]),
            reference_price=float(order["reference_price"]),
            notional=float(order.get("notional", order["quantity"] * order["reference_price"])),
            cost=float(order.get("cost", 0.0)),
            expected_pnl=float(order.get("expected_pnl", 0.0)),
            rationale=str(order.get("rationale", "model-generated hypothesis")),
            timestamp=str(order["timestamp"]),
            order_type=str(order.get("order_type", "model_order")),
        )
        self._orders.append(shadow)
        self._next_id += 1
        self._persist(shadow)
        return shadow

    def list_orders(self, run_id: str | None = None) -> list[dict]:
        if run_id is None:
            return [order.as_record() for order in self._orders]
        return [order.as_record() for order in self._orders if order.run_id == run_id]

    def metrics(self, run_id: str) -> dict:
        returns = [order.expected_pnl / order.notional if order.notional else 0.0
                   for order in self._orders if order.run_id == run_id]
        metrics = _metrics_from_returns(returns)
        metrics.update({
            "run_id": run_id,
            "gross_pnl": sum(order.expected_pnl for order in self._orders if order.run_id == run_id),
            "costs": sum(order.cost for order in self._orders if order.run_id == run_id),
            "executed_orders": 0,
            "mode": "shadow_log_only",
            "broker_execution": False,
        })
        return metrics

    def _persist(self, order: ShadowOrder) -> None:
        append_record(self.log_path, order.as_record())


def replay_audit_log(path: Path) -> list[dict]:
    """Read the append-only shadow audit log; it is data, never an order sink.

    Rotated archives are included so metrics do not drop when a log rotates.
    """
    if not path.is_file():
        return []
    return [record for record in read_records(path)
            if record.get("mode") == "shadow_log_only"]


def make_backtest_config() -> BacktestConfig:
    return BacktestConfig(
        fee_bps=5.0, slippage_bps=2.0,
        initial_capital=10_000.0,
    )


def shadow_metrics_from_log(path: Path) -> dict[str, float]:
    records = replay_audit_log(path)
    returns = [r["expected_pnl"] / r["notional"] if r["notional"] else 0.0 for r in records]
    metrics = _metrics_from_returns(returns)
    metrics.update({
        "shadow_orders": len(records),
        "executed_orders": 0,
        "total_cost": sum(r["cost"] for r in records),
        "mode": "shadow_log_only",
        "broker_execution": False,
    })
    return metrics
