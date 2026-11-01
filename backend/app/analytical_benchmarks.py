"""Reference-vector analytical correctness benchmarks.

These are deterministic formula checks, not predictive or trading-performance tests.
The vectors are intentionally small and independently hand-computable.
"""
from math import isclose
from . import indicators

BENCHMARK_VERSION = "1.0.0"


def run_analytical_benchmarks():
    cases = []

    def check(name, actual, expected, tolerance=1e-9):
        passed = len(actual) == len(expected) and all(
            (a is None and e is None) or
            (a is not None and e is not None and isclose(float(a), float(e), rel_tol=tolerance, abs_tol=tolerance))
            for a, e in zip(actual, expected)
        )
        cases.append({"name": name, "status": "passed" if passed else "failed",
                      "expected": expected, "actual": actual})

    check("sma_partial_window", indicators.sma([1, 2, 3], 2), [1.0, 1.5, 2.5])
    check("ema_recursive", indicators.ema([1, 2, 3], 2), [1.0, 1.6666666666666665, 2.5555555555555554])
    check("simple_returns", indicators.returns([100, 110, 121]), [0.1, 0.1])
    check("rsi_no_losses", indicators.rsi([100, 101, 102, 103], 2), [None, 100.0, 100.0])

    macd = indicators.macd([10, 10, 10, 10], fast=2, slow=3, signal=2)
    check("macd_constant_line", macd["macd"], [0.0, 0.0, 0.0, 0.0])
    check("macd_constant_signal", macd["signal"], [0.0, 0.0, 0.0, 0.0])
    check("macd_constant_histogram", macd["histogram"], [0.0, 0.0, 0.0, 0.0])

    bands = indicators.bollinger([10, 10, 10, 10], period=3, deviations=2)
    check("bollinger_constant_middle", bands["middle"], [10.0] * 4)
    check("bollinger_constant_upper", bands["upper"], [10.0] * 4)
    check("bollinger_constant_lower", bands["lower"], [10.0] * 4)

    volatility = indicators.realized_volatility([100, 110, 121])
    check("realized_volatility_equal_returns", [volatility["per_observation"]], [0.0])

    passed = sum(item["status"] == "passed" for item in cases)
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "status": "passed" if passed == len(cases) else "failed",
        "case_count": len(cases),
        "passed_cases": passed,
        "failed_cases": len(cases) - passed,
        "cases": cases,
        "scope": "formula_and_reference_vector_correctness",
        "limitations": [
            "Small deterministic vectors do not establish robustness on all market regimes.",
            "No predictive skill, profitability, data-provider quality, or execution performance is measured.",
            "The SMA benchmark documents the implementation's current partial-window convention.",
        ],
        "research_only": True,
    }
