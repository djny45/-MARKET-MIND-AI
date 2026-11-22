"""Regime and concept-drift detection (research-only).

Deterministic, dependency-free regime classification from a sequence of returns.
A regime labels the recent distribution of returns as trend-up, trend-down,
high-volatility or low-volatility; drift compares the current window against a
fixed baseline to flag changing market structure.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

DEFAULT_WINDOW = 20
REGIMES = frozenset({"TREND_UP", "TREND_DOWN", "HIGH_VOL", "LOW_VOL", "MIXED"})

MOMENTUM_THRESHOLD = 0.0005  # ~0.05% mean return
VOLATILITY_HIGH_THRESHOLD = 0.004  # 4 bp daily


@dataclass(frozen=True)
class Regime:
    label: str
    momentum: float
    volatility: float
    window: int


def detect_regime(returns: Sequence[float], window: int = DEFAULT_WINDOW) -> Regime:
    """Classify the latest `window` returns using deterministic thresholds."""
    window = max(3, int(window))
    if len(returns) < window:
        raise ValueError("not enough returns for the requested regime window")
    recent = list(returns[-window:])
    mean = sum(recent) / len(recent)
    std = math.sqrt(sum((value - mean) ** 2 for value in recent) / len(recent))
    if mean >= MOMENTUM_THRESHOLD and std < VOLATILITY_HIGH_THRESHOLD:
        label = "TREND_UP"
    elif mean <= -MOMENTUM_THRESHOLD and std < VOLATILITY_HIGH_THRESHOLD:
        label = "TREND_DOWN"
    elif std >= VOLATILITY_HIGH_THRESHOLD:
        label = "HIGH_VOL"
    elif std < 0.25 * VOLATILITY_HIGH_THRESHOLD:
        label = "LOW_VOL"
    else:
        label = "MIXED"
    return Regime(label, mean, std, window)


def drift_report(
    returns: Sequence[float],
    split: float = 0.5,
    window: int = DEFAULT_WINDOW,
) -> dict:
    """Compare the current regime against a baseline and emit a drift score.

    The score is the absolute gap between current momentum and baseline momentum,
    normalized by baseline volatility, or by momentum scale when baseline
    volatility is near zero. Signals a drift when the regime label changes or
    the score exceeds `drift_threshold` (default 1.5).
    """
    drift_threshold = 1.5
    returns = list(returns)
    if len(returns) < 2 * window:
        raise ValueError("not enough returns for a baseline and current window")
    cut = int(len(returns) * split)
    baseline = detect_regime(returns[:cut], window=window)
    current = detect_regime(returns[cut:], window=window)
    denom = baseline.volatility if baseline.volatility > 1e-9 else max(abs(baseline.momentum), 1e-6)
    score = abs(current.momentum - baseline.momentum) / denom
    label_changed = current.label != baseline.label
    return {
        "baseline": {
            "label": baseline.label,
            "momentum": baseline.momentum,
            "volatility": baseline.volatility,
            "window": baseline.window,
        },
        "current": {
            "label": current.label,
            "momentum": current.momentum,
            "volatility": current.volatility,
            "window": current.window,
        },
        "drift_score": round(score, 4),
        "drift_threshold": drift_threshold,
        "signal_drift": score > drift_threshold or label_changed,
        "label_changed": label_changed,
        "research_only": True,
        "broker_execution": False,
    }
