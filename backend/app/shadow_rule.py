"""Mandatory 24-hour shadow rule for new strategies (research-only).

New strategies are shadow-tracked first. Promotion to full evaluation is
invisible until the 24-hour observation window and minimum evaluation
requirements are met. Human approval is always required for promotion
eligibility to become operational status.
"""
from __future__ import annotations

import datetime
from typing import Any

from .shadow_tracker import ShadowTracker
from .research_shadow_session import ShadowSessionEngine, make_backtest_config

MIN_SHADOW_HOURS = 24.0
MIN_EVALUATION_CYCLES = 3


class ShadowRuleEngine:
    def __init__(self, tracker: ShadowTracker | None = None):
        self.tracker = tracker or ShadowTracker(ShadowSessionEngine(make_backtest_config()))
        self.registered_at: dict[str, str] = {}
        self._now_fn = lambda: datetime.datetime.now(datetime.timezone.utc)

    def register_strategy(self, symbol: str) -> str:
        if not symbol or not isinstance(symbol, str):
            raise ValueError("symbol is required")
        self.registered_at[symbol] = self._now_iso()
        return symbol

    def hours_elapsed(self, symbol: str) -> float:
        if symbol not in self.registered_at:
            raise ValueError(f"{symbol} is not registered for shadow tracking")
        start = datetime.datetime.fromisoformat(self.registered_at[symbol].replace("Z", "+00:00"))
        return (self._now_utc() - start).total_seconds() / 3600.0

    def cycles(self, symbol: str) -> int:
        return len(self.tracker.daily_report(symbol=symbol))

    def total_pnl(self, symbol: str) -> float:
        return sum(row.total_pnl for row in self.tracker.daily_report(symbol=symbol))

    def failed_cycles(self, symbol: str) -> int:
        return sum(1 for row in self.tracker.daily_report(symbol=symbol) if row.total_pnl < 0)

    def passed_minimum_evaluation(self, symbol: str) -> bool:
        if self.cycles(symbol) < MIN_EVALUATION_CYCLES:
            return False
        if self.failed_cycles(symbol) > 0:
            return False
        return True

    def promotion_eligibility(self, symbol: str) -> dict[str, Any]:
        if symbol not in self.registered_at:
            raise ValueError(f"{symbol} is not registered for shadow tracking")
        hours = self.hours_elapsed(symbol)
        cycles = self.cycles(symbol)
        pnl = self.total_pnl(symbol)
        failed = self.failed_cycles(symbol)
        return {
            "symbol": symbol,
            "min_shadow_hours": MIN_SHADOW_HOURS,
            "hours_elapsed": round(hours, 3),
            "min_evaluation_cycles": MIN_EVALUATION_CYCLES,
            "evaluation_cycles": cycles,
            "total_shadow_pnl": round(pnl, 4),
            "failed_cycles": failed,
            "window_complete": hours >= MIN_SHADOW_HOURS,
            "minimum_met": self.passed_minimum_evaluation(symbol),
            "eligible_for_review": self.passed_minimum_evaluation(symbol) and hours >= MIN_SHADOW_HOURS,
            "requires_human_approval": True,
            "research_only": True,
            "broker_execution": False,
        }

    def promotion_reports(self) -> list[dict[str, Any]]:
        return [self.promotion_eligibility(symbol) for symbol in sorted(self.registered_at)]

    def isolate_strategy(self, symbol: str, run_id: str) -> str:
        self.tracker.begin_run(run_id, symbol)
        return run_id

    def report(self) -> dict:
        return {
            "strategies": self.promotion_reports(),
            "eligible_for_review": [s for s in self.promotion_reports() if s["eligible_for_review"]],
            "research_only": True,
            "broker_execution": False,
        }

    def _now_utc(self) -> datetime.datetime:
        now = self._now_fn()
        return now if now.tzinfo else now.replace(tzinfo=datetime.timezone.utc)

    def _now_iso(self) -> str:
        return self._now_utc().isoformat()

    _now_fn = staticmethod(lambda: datetime.datetime.now(datetime.timezone.utc))


def make_rule_engine(**kwargs) -> ShadowRuleEngine:
    return ShadowRuleEngine(tracker=ShadowTracker(ShadowSessionEngine(make_backtest_config())), **kwargs)
