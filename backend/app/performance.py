"""Descriptive portfolio-style statistics for research datasets, not trade advice."""
from math import isfinite, sqrt

from .indicators import returns


def _finite(values, name):
    xs = [float(value) for value in values]
    if not xs:
        raise ValueError(f"{name} must not be empty")
    if any(not isfinite(value) for value in xs):
        raise ValueError(f"{name} must contain finite numbers")
    return xs


def max_drawdown(prices):
    xs = _finite(prices, "prices")
    if any(value <= 0 for value in xs):
        raise ValueError("prices must be positive")
    peak = xs[0]
    worst = 0.0
    for value in xs:
        peak = max(peak, value)
        worst = min(worst, value / peak - 1.0)
    return worst


def performance_metrics(prices, benchmark=None, periods_per_year=None, risk_free_rate=0.0):
    xs = _finite(prices, "prices")
    if len(xs) < 3:
        raise ValueError("At least three prices are required")
    if any(value <= 0 for value in xs):
        raise ValueError("prices must be positive")

    risk_free = float(risk_free_rate)
    if not isfinite(risk_free):
        raise ValueError("risk_free_rate must be finite")

    rs = _finite(returns(xs), "price returns")
    mean = sum(rs) / len(rs)
    variance = sum((value - mean) ** 2 for value in rs) / (len(rs) - 1)
    volatility = sqrt(variance)
    downside = [min(value, 0.0) for value in rs]
    downside_deviation = sqrt(sum(value * value for value in downside) / len(downside))
    excess = mean - risk_free
    cumulative_return = xs[-1] / xs[0] - 1.0
    if not isfinite(cumulative_return):
        raise ValueError("price range exceeds supported numeric precision")
    out = {
        "observations": len(xs),
        "return_observations": len(rs),
        "cumulative_return": cumulative_return,
        "mean_period_return": mean,
        "sample_volatility": volatility,
        "max_drawdown": max_drawdown(xs),
        "sharpe_per_period": excess / volatility if volatility else None,
        "sortino_per_period": excess / downside_deviation if downside_deviation else None,
        "annualized_sharpe": None,
        "annualized_volatility": None,
        "beta": None,
        "correlation_to_benchmark": None,
        "scope": "Historical descriptive statistics; not a forecast or recommendation.",
    }

    if periods_per_year is not None:
        periods = float(periods_per_year)
        if not isfinite(periods) or periods <= 0:
            raise ValueError("periods_per_year must be finite and positive")
        out["annualized_sharpe"] = (excess / volatility) * sqrt(periods) if volatility else None
        out["annualized_volatility"] = volatility * sqrt(periods)

    if benchmark is not None:
        benchmark_prices = _finite(benchmark, "benchmark")
        if len(benchmark_prices) < 3:
            raise ValueError("At least three benchmark prices are required")
        if any(value <= 0 for value in benchmark_prices):
            raise ValueError("benchmark prices must be positive")
        benchmark_returns = _finite(returns(benchmark_prices), "benchmark returns")
        if len(benchmark_returns) != len(rs):
            raise ValueError("benchmark must have the same number of return observations")
        benchmark_mean = sum(benchmark_returns) / len(benchmark_returns)
        benchmark_variance = sum(
            (value - benchmark_mean) ** 2 for value in benchmark_returns
        ) / (len(benchmark_returns) - 1)
        covariance = sum(
            (asset_return - mean) * (benchmark_return - benchmark_mean)
            for asset_return, benchmark_return in zip(rs, benchmark_returns)
        ) / (len(rs) - 1)
        out["beta"] = covariance / benchmark_variance if benchmark_variance else None
        out["correlation_to_benchmark"] = (
            covariance / (volatility * sqrt(benchmark_variance))
            if volatility and benchmark_variance else None
        )
    for name, value in out.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool) and not isfinite(value):
            raise ValueError(f"{name} exceeds supported numeric precision")
    return out
