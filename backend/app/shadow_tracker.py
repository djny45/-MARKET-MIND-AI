"""Shadow-tracking and demotion-cycle automation (research-only).

Tracks daily simulated performance for shadow-tracked strategies and applies
ten-cycle demotion rules. All data comes from the deterministic shadow-order
engine; there is no execution path.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable

from .audit_jsonl import append_record
from .research_shadow_session import ShadowSessionEngine, make_backtest_config

DEMOTION_THRESHOLD_CYCLES = 10
CLEAN_RECOVERY_CYCLES = 10
AUDIT_PATH = Path(os.getenv("MARKET_MIND_DB", "./data/market_mind.db")).with_name(
    "shadow_tracker_audit.jsonl"
)


@dataclass
class DailyShadowSnapshot:
    date: str
    symbol: str
    run_id: str
    total_pnl: float
    costs: float
    order_count: int
    sharpe: float
    sortino: float
    max_drawdown: float


@dataclass
class StrategyEvaluation:
    symbol: str
    daily_snapshots: list[DailyShadowSnapshot]
    consecutive_failing_cycles: int
    recovery_cycles: int
    status: str  # "tracked", "demoted", "recovered"
    demote_now: bool


@dataclass
class DemotionProposal:
    symbol: str
    reason: str
    consecutive_failing_cycles: int
    recommended_action: str  # demote or suspend
    proposed_by: str  # system-generated
    human_required: bool


class ShadowTracker:
    """Aggregates shadow orders into daily performance and applies demotion cycles."""

    def __init__(self, engine: ShadowSessionEngine, audit_path: Path | None = None):
        engine.config.validate()
        self.engine = engine
        self.audit_path = Path(audit_path) if audit_path else AUDIT_PATH
        self._demoted: set[str] = set()
        self._recovered: set[str] = set()
        self._audit_counter = 0

    def begin_run(self, run_id: str, symbol: str) -> str:
        return self.engine.begin_run(run_id)

    def record_shadow_order(self, symbol: str, order: dict, run_id: str) -> int:
        self.engine.record_shadow_order({**order, "symbol": symbol}, run_id=run_id)
        return len(self.engine.list_orders(run_id))

    def daily_report(self, run_id: str | None = None, symbol: str | None = None) -> list[DailyShadowSnapshot]:
        rows: list[DailyShadowSnapshot] = []
        for order in sorted(
            self.engine.list_orders(run_id), key=lambda record: record["id"]
        ):
            day = str(order["timestamp"])[:10]
            order_symbol = order["symbol"]
            rows.append(
                DailyShadowSnapshot(
                    date=day,
                    symbol=order_symbol,
                    run_id=run_id,
                    total_pnl=order["expected_pnl"],
                    costs=order["cost"],
                    order_count=1,
                    sharpe=0.0,
                    sortino=0.0,
                    max_drawdown=0.0,
                )
            )
        if symbol:
            rows = [row for row in rows if row.symbol == symbol]
        grouped: dict[tuple[str, str], DailyShadowSnapshot] = {}
        for row in rows:
            key = (row.date, row.symbol)
            if key not in grouped:
                grouped[key] = DailyShadowSnapshot(
                    date=row.date, symbol=row.symbol, run_id=row.run_id,
                    total_pnl=0.0, costs=0.0, order_count=0,
                    sharpe=0.0, sortino=0.0, max_drawdown=0.0,
                )
            aggregated = grouped[key]
            aggregated.total_pnl += row.total_pnl
            aggregated.costs += row.costs
            aggregated.order_count += row.order_count
        for snapshot in grouped.values():
            if snapshot.order_count:
                snapshot.sharpe = snapshot.total_pnl / snapshot.order_count
        return sorted(grouped.values(), key=lambda row: (row.date, row.symbol))

    def performance_history(self, symbol: str) -> list[DailyShadowSnapshot]:
        return [row for row in self.daily_report("") if row.symbol == symbol]

    def demoted_symbols(self) -> set[str]:
        return set(self._demoted)

    def evaluate_strategies(self) -> dict[str, StrategyEvaluation]:
        """Evaluate all tracked symbols against the ten-cycle demotion rule."""
        all_rows = self.daily_report()
        symbols = {row.symbol for row in all_rows}
        history: dict[str, list[DailyShadowSnapshot]] = {}
        for symbol in symbols:
            history[symbol] = [row for row in all_rows if row.symbol == symbol]
        evaluations: dict[str, StrategyEvaluation] = {}
        for symbol in sorted(history):
            snapshots = history[symbol]
            failing = 0
            recovering = 0
            baseline = self._baseline_sharpe(snapshots[:5]) if len(snapshots) >= 5 else 0.0
            for snapshot in snapshots:
                is_failing = self._fails_cycle(snapshot, baseline)
                if is_failing:
                    failing += 1
                    recovering = 0
                else:
                    recovering += 1
                    if symbol in self._demoted and recovering >= CLEAN_RECOVERY_CYCLES:
                        self._demoted.discard(symbol)
                        self._recovered.add(symbol)
                        self._persist("recovered", symbol, reason=f"{recovering} clean cycles")
            status = (
                "recovered" if symbol in self._recovered
                else "demoted" if symbol in self._demoted
                else "tracked"
            )
            evaluations[symbol] = StrategyEvaluation(
                symbol=symbol,
                daily_snapshots=snapshots,
                consecutive_failing_cycles=failing,
                recovery_cycles=recovering,
                status=status,
                demote_now=failing >= DEMOTION_THRESHOLD_CYCLES,
            )
        return evaluations

    def generate_demotion_proposals(self) -> list[DemotionProposal]:
        proposals: list[DemotionProposal] = []
        for symbol, evaluation in self.evaluate_strategies().items():
            if evaluation.demote_now and symbol not in self._demoted:
                proposal = DemotionProposal(
                    symbol=symbol,
                    reason=f"{evaluation.consecutive_failing_cycles} consecutive failing cycles",
                    consecutive_failing_cycles=evaluation.consecutive_failing_cycles,
                    recommended_action="demote",
                    proposed_by="automated-system",
                    human_required=True,
                )
                proposals.append(proposal)
                self._persist("demotion_proposed", symbol, reason=proposal.reason)
        return proposals

    def demote(self, symbol: str, reviewer: str, reason: str) -> dict:
        if symbol not in {row.symbol for row in self.daily_report()}:
            raise ValueError(f"unknown symbol: {symbol}")
        self._demoted.add(symbol)
        self._persist("demoted", symbol, reason=f"{reason} (by {reviewer})")
        return {"symbol": symbol, "status": "demoted", "reviewer": reviewer, "reason": reason}

    def recover(self, symbol: str, reviewer: str, reason: str) -> dict:
        if symbol not in {row.symbol for row in self.daily_report()}:
            raise ValueError(f"unknown symbol: {symbol}")
        if symbol not in self._demoted:
            self._recovered.add(symbol)
            self._persist("recovered", symbol, reason=f"{reason} (by {reviewer})")
            return {"symbol": symbol, "status": "recovered", "reviewer": reviewer, "reason": reason}
        self._demoted.discard(symbol)
        self._recovered.add(symbol)
        self._persist("recovered", symbol, reason=f"{reason} (by {reviewer})")
        return {"symbol": symbol, "status": "recovered", "reviewer": reviewer, "reason": reason}

    def report(self) -> dict:
        evaluations = self.evaluate_strategies()
        self._persist("report", "-", reason="daily_report")
        return {
            "symbols_tracked": len(evaluations),
            "demoted": sorted(self._demoted),
            "demotion_cycle_limit": DEMOTION_THRESHOLD_CYCLES,
            "recovery_cycle_limit": CLEAN_RECOVERY_CYCLES,
            "cycles": {
                symbol: {
                    "consecutive_failing_cycles": evaluation.consecutive_failing_cycles,
                    "recovery_cycles": evaluation.recovery_cycles,
                    "status": evaluation.status,
                }
                for symbol, evaluation in evaluations.items()
            },
            "research_only": True,
            "broker_execution": False,
        }

    def _baseline_sharpe(self, snapshots: list[DailyShadowSnapshot]) -> float:
        recent = snapshots[-5:]
        return sum(snapshot.sharpe for snapshot in recent) / len(recent) if recent else 0.0

    def _fails_cycle(self, snapshot: DailyShadowSnapshot, baseline: float) -> bool:
        if snapshot.order_count == 0:
            return False
        return snapshot.total_pnl < 0 or snapshot.sharpe < baseline

    def _persist(self, event: str, symbol: str, reason: str) -> None:
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        self._audit_counter += 1
        record = {
            "event": event,
            "symbol": symbol,
            "reason": reason,
            "persisted_id": self._audit_counter,
        }
        append_record(self.audit_path, record)


def read_tracker_audit(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def make_tracker(**kwargs) -> ShadowTracker:
    return ShadowTracker(engine=ShadowSessionEngine(make_backtest_config()), **kwargs)
