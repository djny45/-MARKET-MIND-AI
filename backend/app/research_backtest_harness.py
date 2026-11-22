"""Deterministic, research-only backtesting harness.

No broker connection, no order routing, no capital at risk. Every order produced
here is a *shadow order*: a log record only. The harness enforces chronological
splits, explicit costs, out-of-sample evaluation, multiple-testing correction and
a reproducibility manifest so strategy decisions can be audited.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass, field
from typing import Callable, Iterable, Sequence

SignalFn = Callable[[Sequence["Bar"]], int]


@dataclass(frozen=True)
class Bar:
    timestamp: str
    close: float
    high: float
    low: float
    volume: float = 0.0


@dataclass(frozen=True)
class BacktestConfig:
    train_fraction: float = 0.5
    validation_fraction: float = 0.25
    fee_bps: float = 5.0
    slippage_bps: float = 2.0
    initial_capital: float = 10_000.0
    seed: int = 0

    def validate(self) -> None:
        if not 0 < self.train_fraction < 1:
            raise ValueError("train_fraction must be between 0 and 1")
        if not 0 < self.validation_fraction < 1:
            raise ValueError("validation_fraction must be between 0 and 1")
        if self.train_fraction + self.validation_fraction >= 0.95:
            raise ValueError("train and validation fractions leave no test window")
        if self.fee_bps < 0 or self.slippage_bps < 0:
            raise ValueError("cost assumptions cannot be negative")
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")


@dataclass
class Hypothesis:
    id: str
    statement: str
    parameters: dict = field(default_factory=dict)
    status: str = "proposed"
    created_at: str = ""


class HypothesisRegistry:
    """Append-only in-memory registry; callers can persist the exported records."""

    def __init__(self) -> None:
        self._records: dict[str, Hypothesis] = {}

    def register(self, hypothesis: Hypothesis) -> Hypothesis:
        if hypothesis.id in self._records:
            raise ValueError("duplicate hypothesis id")
        self._records[hypothesis.id] = hypothesis
        return hypothesis

    def update(self, hypothesis_id: str, status: str) -> Hypothesis:
        if hypothesis_id not in self._records:
            raise KeyError(hypothesis_id)
        old = self._records[hypothesis_id]
        self._records[hypothesis_id] = Hypothesis(
            old.id, old.statement, old.parameters, status, old.created_at
        )
        return self._records[hypothesis_id]

    def list(self) -> list[dict]:
        return [asdict(item) for item in self._records.values()]


def generate_synthetic_bars(count: int = 500, seed: int = 0, start_price: float = 100.0) -> list[Bar]:
    """Generate deterministic synthetic OHLCV bars for harness validation."""
    if count < 100:
        raise ValueError("count must be at least 100")
    rng = random.Random(seed)
    price = start_price
    bars: list[Bar] = []
    for index in range(count):
        drift = 0.0004 if index % 37 < 19 else -0.0003
        change = rng.gauss(drift, 0.012)
        price = max(0.01, price * (1 + change))
        high = price * (1 + abs(rng.gauss(0, 0.004)))
        low = price * (1 - abs(rng.gauss(0, 0.004)))
        bars.append(Bar(f"2026-01-01T{index:06d}", price, high, low, 1000.0))
    return bars


def split_bars(bars: Sequence[Bar], config: BacktestConfig) -> dict[str, list[Bar]]:
    """Chronological train / validation / test split; never shuffles."""
    config.validate()
    n = len(bars)
    train_end = int(n * config.train_fraction)
    val_end = train_end + int(n * config.validation_fraction)
    if train_end < 10 or val_end - train_end < 10 or n - val_end < 10:
        raise ValueError("dataset too small for the requested split")
    return {
        "train": list(bars[:train_end]),
        "validation": list(bars[train_end:val_end]),
        "test": list(bars[val_end:]),
    }


def _returns(bars: Sequence[Bar]) -> list[float]:
    return [
        (bars[i].close / bars[i - 1].close) - 1
        for i in range(1, len(bars))
        if bars[i - 1].close > 0
    ]


def _metrics(equity: list[float]) -> dict[str, float]:
    returns = [
        equity[i] / equity[i - 1] - 1
        for i in range(1, len(equity))
        if equity[i - 1] > 0
    ]
    if not returns:
        return {"total_return": 0.0, "sharpe": 0.0, "sortino": 0.0, "max_drawdown": 0.0}
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / len(returns)
    std = math.sqrt(variance)
    downside = [r for r in returns if r < 0]
    down_dev = math.sqrt(sum(r * r for r in downside) / len(returns)) if downside else 0.0
    peak = equity[0]
    max_dd = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            max_dd = min(max_dd, value / peak - 1)
    return {
        "total_return": equity[-1] / equity[0] - 1,
        "sharpe": (mean / std * math.sqrt(252)) if std else 0.0,
        "sortino": (mean / down_dev * math.sqrt(252)) if down_dev else 0.0,
        "max_drawdown": max_dd,
    }


def run_backtest(
    bars: Sequence[Bar], signal_fn: SignalFn, config: BacktestConfig
) -> dict:
    """Simulate a long/flat strategy with costs and emit shadow orders only."""
    config.validate()
    if len(bars) < 20:
        raise ValueError("at least 20 bars are required")
    equity = config.initial_capital
    position = 0
    equity_curve = [equity]
    shadow_orders: list[dict] = []
    cost_rate = (config.fee_bps + config.slippage_bps) / 10_000
    for index in range(1, len(bars)):
        target = int(signal_fn(list(bars[:index])))
        target = 1 if target > 0 else 0  # long/flat only; no shorting or leverage
        bar = bars[index]
        if target != position:
            notional = equity * abs(target - position)
            cost = notional * cost_rate
            equity -= cost
            shadow_orders.append({
                "index": index,
                "timestamp": bar.timestamp,
                "side": "BUY" if target else "SELL",
                "notional": round(notional, 6),
                "reference_price": bar.close,
                "cost": round(cost, 6),
                "executed": False,
                "mode": "shadow_log_only",
            })
            position = target
        if index < len(bars) - 1:
            ret = (bars[index + 1].close / bar.close) - 1
            equity *= 1 + position * ret
        equity_curve.append(equity)

    payload = {
        "bars": [asdict(bar) for bar in bars],
        "config": asdict(config),
        "orders": shadow_orders,
    }
    data_digest = hashlib.sha256(
        json.dumps([bar.close for bar in bars], sort_keys=True).encode()
    ).hexdigest()
    config_digest = hashlib.sha256(
        json.dumps(asdict(config), sort_keys=True).encode()
    ).hexdigest()
    return {
        **_metrics(equity_curve),
        "equity_curve": equity_curve,
        "shadow_orders": shadow_orders,
        "trade_count": len(shadow_orders),
        "final_equity": equity,
        "manifest": {
            "data_digest": data_digest,
            "config_digest": config_digest,
            "bar_count": len(bars),
            "seed": config.seed,
            "cost_model_bps": config.fee_bps + config.slippage_bps,
            "payload_digest": hashlib.sha256(
                json.dumps(payload, sort_keys=True).encode()
            ).hexdigest(),
        },
        "research_only": True,
        "broker_execution": False,
    }


def _approximately_normal_pvalue(t_statistic: float) -> float:
    """Two-sided approximate p-value from the normal tail; no scipy dependency."""
    return math.erfc(abs(t_statistic) / math.sqrt(2))


def benjamini_hochberg(pvalues: Sequence[float]) -> list[float]:
    """Return BH-adjusted q-values in the original order."""
    if not pvalues:
        return []
    order = sorted(range(len(pvalues)), key=lambda i: pvalues[i])
    adjusted = [0.0] * len(pvalues)
    previous = 1.0
    for rank, index in enumerate(reversed(order), start=1):
        position = len(pvalues) - rank + 1
        value = min(previous, pvalues[index] * len(pvalues) / position)
        adjusted[index] = min(1.0, value)
        previous = value
    return adjusted


def evaluate_candidates(
    bars: Sequence[Bar],
    candidates: dict[str, SignalFn],
    config: BacktestConfig,
    *,
    significance_level: float = 0.05,
) -> dict:
    """Select on train+validation, evaluate once on untouched test data.

    Raw p-values come from an approximate Sharpe t-statistic and are corrected
    with Benjamini-Hochberg across all candidates. Promotion requires corrected
    significance on the test window and a strictly positive test Sharpe.
    """
    if not candidates:
        raise ValueError("at least one candidate is required")
    splits = split_bars(bars, config)
    development = splits["train"] + splits["validation"]
    results: list[dict] = []
    for name, signal_fn in candidates.items():
        dev = run_backtest(development, signal_fn, config)
        test = run_backtest(splits["test"], signal_fn, config)
        n = len(_returns(splits["test"]))
        t_stat = test["sharpe"] * math.sqrt(max(n, 1))
        results.append({
            "name": name,
            "development_sharpe": dev["sharpe"],
            "test_sharpe": test["sharpe"],
            "test_total_return": test["total_return"],
            "test_max_drawdown": test["max_drawdown"],
            "test_trade_count": test["trade_count"],
            "p_value": _approximately_normal_pvalue(t_stat),
            "test_manifest": test["manifest"],
            "shadow_orders": test["shadow_orders"],
        })
    qvalues = benjamini_hochberg([item["p_value"] for item in results])
    for item, qvalue in zip(results, qvalues):
        item["q_value"] = qvalue
        item["promote"] = (
            qvalue < significance_level
            and item["test_sharpe"] > 0
            and item["test_trade_count"] > 0
        )
    results.sort(key=lambda item: item["test_sharpe"], reverse=True)
    return {
        "candidates": results,
        "significance_level": significance_level,
        "correction": "benjamini_hochberg",
        "promoted": [item["name"] for item in results if item["promote"]],
        "research_only": True,
        "broker_execution": False,
    }


def momentum_signal(lookback: int = 10) -> SignalFn:
    """Long when the last close exceeds the close `lookback` bars ago."""
    def signal(history: Sequence[Bar]) -> int:
        if len(history) <= lookback:
            return 0
        return 1 if history[-1].close > history[-1 - lookback].close else 0
    return signal


def mean_reversion_signal(lookback: int = 10) -> SignalFn:
    """Long when price is below its simple moving average (paper research only)."""
    def signal(history: Sequence[Bar]) -> int:
        if len(history) < lookback:
            return 0
        window = [bar.close for bar in history[-lookback:]]
        mean = sum(window) / len(window)
        return 1 if history[-1].close < mean else 0
    return signal
