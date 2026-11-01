"""Reference-based correctness checks for deterministic indicator implementations.

Fixtures are deterministic and synthetic. Passing means agreement with these
reference cases, not predictive quality or live-market validity.
"""
from math import isclose, sqrt

from .indicators import (
    sma, ema, returns, rsi, macd, bollinger, realized_volatility,
)

TOLERANCE = 1e-9


def _close(actual, expected, tolerance=TOLERANCE):
    return len(actual) == len(expected) and all(
        (a is None and e is None)
        or (
            a is not None and e is not None
            and isclose(float(a), float(e), rel_tol=tolerance, abs_tol=tolerance)
        )
        for a, e in zip(actual, expected)
    )


def run_indicator_benchmarks():
    cases = []

    def record(name, passed, expected, actual, note=""):
        cases.append({
            "case": name,
            "status": "passed" if passed else "failed",
            "expected": expected,
            "actual": actual,
            "note": note,
        })

    prices = [100.0, 101.0, 102.0, 103.0, 104.0]
    expected_sma = [100.0, 100.5, 101.5, 102.5, 103.5]
    actual_sma = sma(prices, 2)
    record("sma_period_2", _close(actual_sma, expected_sma), expected_sma, actual_sma)

    expected_ema = [
        100.0, 100.66666666666667, 101.55555555555556,
        102.51851851851852, 103.50617283950618,
    ]
    actual_ema = ema(prices, 2)
    record("ema_period_2", _close(actual_ema, expected_ema), expected_ema, actual_ema)

    expected_returns = [
        0.01, 102.0 / 101.0 - 1, 103.0 / 102.0 - 1, 104.0 / 103.0 - 1,
    ]
    actual_returns = returns(prices)
    record("simple_returns", _close(actual_returns, expected_returns),
           expected_returns, actual_returns)

    rising = rsi([1.0, 2.0, 3.0, 4.0], 2)
    record("rsi_monotonic_rise", _close(rising, [None, 100.0, 100.0]),
           [None, 100.0, 100.0], rising)

    falling = rsi([4.0, 3.0, 2.0, 1.0], 2)
    record("rsi_monotonic_decline", _close(falling, [None, 0.0, 0.0]),
           [None, 0.0, 0.0], falling)

    flat = rsi([10.0, 10.0, 10.0, 10.0], 2)
    record("rsi_flat_neutral", _close(flat, [None, 50.0, 50.0]),
           [None, 50.0, 50.0], flat,
           "A window with zero average gain and zero average loss is neutral.")

    mixed = rsi([100.0, 110.0, 100.0], 2)
    expected_mixed = [None, 52.38095238095238]
    record("rsi_mixed_gain_loss", _close(mixed, expected_mixed),
           expected_mixed, mixed)

    macd_result = macd(prices, fast=2, slow=3, signal=2)
    macd_shape = (
        len(macd_result["macd"]) == len(prices)
        and len(macd_result["signal"]) == len(prices)
        and len(macd_result["histogram"]) == len(prices)
        and _close(
            macd_result["histogram"],
            [a - b for a, b in zip(macd_result["macd"], macd_result["signal"])],
        )
    )
    record("macd_component_consistency", macd_shape,
           "equal-length series; histogram = MACD - signal",
           {"lengths": [len(macd_result[k]) for k in ("macd", "signal", "histogram")]})

    bands = bollinger([10.0, 10.0, 10.0], period=3, deviations=2)
    band_ok = (
        _close(bands["middle"], [10.0, 10.0, 10.0])
        and _close(bands["upper"], [10.0, 10.0, 10.0])
        and _close(bands["lower"], [10.0, 10.0, 10.0])
    )
    record("bollinger_zero_variance", band_ok, "all bands equal 10", bands)

    vol = realized_volatility([100.0, 101.0, 100.0, 102.0])
    rs = returns([100.0, 101.0, 100.0, 102.0])
    mean = sum(rs) / len(rs)
    expected_vol = sqrt(sum((x - mean) ** 2 for x in rs) / (len(rs) - 1))
    vol_ok = isclose(
        vol["per_observation"], expected_vol,
        rel_tol=TOLERANCE, abs_tol=TOLERANCE,
    )
    record("sample_realized_volatility", vol_ok, expected_vol, vol["per_observation"])

    passed = sum(item["status"] == "passed" for item in cases)
    return {
        "benchmark_version": "1.1.0",
        "status": "passed" if passed == len(cases) else "failed",
        "mode": "deterministic_reference_fixture",
        "passed": passed,
        "failed": len(cases) - passed,
        "total": len(cases),
        "tolerance": TOLERANCE,
        "cases": cases,
        "limitations": [
            "Synthetic fixtures only; no live market data or external library oracle.",
            "These cases test selected formula contracts and edge conditions, not exhaustive correctness.",
            "Passing does not establish predictive performance or suitability for investment decisions.",
        ],
        "research_only": True,
    }
