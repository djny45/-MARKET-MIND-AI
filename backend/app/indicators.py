"""Dependency-light deterministic indicators over chronological numeric observations."""
from math import isfinite, sqrt


def _checked(values, name):
    result = list(values)
    if any(value is not None and not isfinite(value) for value in result):
        raise ValueError(f"{name} exceeds supported numeric precision")
    return result


def _valid(values, minimum=1):
    xs = [float(value) for value in values]
    if len(xs) < minimum:
        raise ValueError(f"At least {minimum} observations are required.")
    if any(not isfinite(value) for value in xs):
        raise ValueError("observations must contain finite numbers")
    return xs


def sma(values, period):
    xs = _valid(values)
    p = int(period)
    if p < 1:
        raise ValueError("period must be positive")
    result = [
        sum(xs[max(0, i - p + 1):i + 1]) / len(xs[max(0, i - p + 1):i + 1])
        for i in range(len(xs))
    ]
    return _checked(result, "simple moving average")


def ema(values, period):
    xs = _valid(values)
    p = int(period)
    if p < 1:
        raise ValueError("period must be positive")
    alpha = 2 / (p + 1)
    result = [xs[0]]
    for value in xs[1:]:
        result.append(alpha * value + (1 - alpha) * result[-1])
    return _checked(result, "exponential moving average")


def returns(values):
    xs = _valid(values, 2)
    if any(value == 0 for value in xs[:-1]):
        raise ValueError("zero denominator in price series")
    result = [xs[i] / xs[i - 1] - 1 for i in range(1, len(xs))]
    return _checked(result, "price returns")


def rsi(values, period=14):
    rs = returns(values)
    p = int(period)
    if p < 1:
        raise ValueError("period must be positive")
    if len(rs) < p:
        return [None] * len(rs)
    gains = [max(value, 0) for value in rs]
    losses = [max(-value, 0) for value in rs]
    average_gain = sum(gains[:p]) / p
    average_loss = sum(losses[:p]) / p
    result = [None] * (p - 1)
    result.append(100.0 if average_loss == 0 else 100 - 100 / (1 + average_gain / average_loss))
    for i in range(p, len(rs)):
        average_gain = (average_gain * (p - 1) + gains[i]) / p
        average_loss = (average_loss * (p - 1) + losses[i]) / p
        result.append(100.0 if average_loss == 0 else 100 - 100 / (1 + average_gain / average_loss))
    return _checked(result, "relative strength index")


def macd(values, fast=12, slow=26, signal=9):
    line = [a - b for a, b in zip(ema(values, fast), ema(values, slow))]
    signal_line = ema(line, signal)
    return {
        "macd": _checked(line, "MACD"),
        "signal": signal_line,
        "histogram": _checked(
            [a - b for a, b in zip(line, signal_line)], "MACD histogram"
        ),
    }


def bollinger(values, period=20, deviations=2):
    xs = _valid(values)
    p = int(period)
    if p < 1:
        raise ValueError("period must be positive")
    deviation_multiplier = float(deviations)
    if not isfinite(deviation_multiplier) or deviation_multiplier < 0:
        raise ValueError("deviations must be finite and non-negative")
    middle = sma(xs, p)
    upper = []
    lower = []
    for i, mean in enumerate(middle):
        window = xs[max(0, i - p + 1):i + 1]
        standard_deviation = sqrt(
            sum((value - mean) ** 2 for value in window) / len(window)
        )
        upper.append(mean + deviation_multiplier * standard_deviation)
        lower.append(mean - deviation_multiplier * standard_deviation)
    return {
        "middle": middle,
        "upper": _checked(upper, "Bollinger upper band"),
        "lower": _checked(lower, "Bollinger lower band"),
    }


def realized_volatility(prices, annualization=None):
    rs = returns(prices)
    if len(rs) < 2:
        raise ValueError("At least two returns are required.")
    mean = sum(rs) / len(rs)
    variance = sum((value - mean) ** 2 for value in rs) / (len(rs) - 1)
    volatility = sqrt(variance)
    result = {"per_observation": volatility, "observations": len(rs)}
    if annualization is not None:
        periods = float(annualization)
        if not isfinite(periods) or periods <= 0:
            raise ValueError("annualization must be finite and positive")
        result["annualized"] = sqrt(variance * periods)
    _checked([value for value in result.values() if isinstance(value, (int, float))],
             "realized volatility")
    return result
