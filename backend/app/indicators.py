"""Dependency-light deterministic indicators over chronological numeric observations."""
from math import isfinite, sqrt


def _valid(values, minimum=1):
    try:
        xs = [float(x) for x in values]
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("observations must be finite numeric values") from exc
    if len(xs) < minimum:
        raise ValueError(f"At least {minimum} observations are required.")
    if not all(isfinite(value) for value in xs):
        raise ValueError("observations must be finite numeric values")
    return xs


def sma(values, period):
    xs = _valid(values)
    p = int(period)
    if p < 1:
        raise ValueError("period must be positive")
    return [
        sum(xs[max(0, i - p + 1):i + 1]) / len(xs[max(0, i - p + 1):i + 1])
        for i in range(len(xs))
    ]


def ema(values, period):
    xs = _valid(values)
    p = int(period)
    if p < 1:
        raise ValueError("period must be positive")
    alpha = 2 / (p + 1)
    out = [xs[0]]
    for value in xs[1:]:
        out.append(alpha * value + (1 - alpha) * out[-1])
    return out


def returns(values):
    xs = _valid(values, 2)
    if any(value == 0 for value in xs[:-1]):
        raise ValueError("zero denominator in price series")
    return [xs[i] / xs[i - 1] - 1 for i in range(1, len(xs))]


def _rsi_value(average_gain, average_loss):
    # A flat window has neither gains nor losses and is therefore neutral.
    if average_gain == 0 and average_loss == 0:
        return 50.0
    if average_loss == 0:
        return 100.0
    if average_gain == 0:
        return 0.0
    relative_strength = average_gain / average_loss
    return 100 - 100 / (1 + relative_strength)


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
    out = [None] * (p - 1)
    out.append(_rsi_value(average_gain, average_loss))
    for i in range(p, len(rs)):
        average_gain = (average_gain * (p - 1) + gains[i]) / p
        average_loss = (average_loss * (p - 1) + losses[i]) / p
        out.append(_rsi_value(average_gain, average_loss))
    return out


def macd(values, fast=12, slow=26, signal=9):
    line = [a - b for a, b in zip(ema(values, fast), ema(values, slow))]
    signal_line = ema(line, signal)
    return {
        "macd": line,
        "signal": signal_line,
        "histogram": [a - b for a, b in zip(line, signal_line)],
    }


def bollinger(values, period=20, deviations=2):
    xs = _valid(values)
    p = int(period)
    if p < 1:
        raise ValueError("period must be positive")
    middle = sma(xs, p)
    upper, lower = [], []
    for i, mean in enumerate(middle):
        window = xs[max(0, i - p + 1):i + 1]
        standard_deviation = sqrt(
            sum((value - mean) ** 2 for value in window) / len(window)
        )
        upper.append(mean + deviations * standard_deviation)
        lower.append(mean - deviations * standard_deviation)
    return {"middle": middle, "upper": upper, "lower": lower}


def realized_volatility(prices, annualization=None):
    rs = returns(prices)
    if len(rs) < 2:
        raise ValueError("At least two returns are required.")
    mean = sum(rs) / len(rs)
    variance = sum((value - mean) ** 2 for value in rs) / (len(rs) - 1)
    out = {"per_observation": sqrt(variance), "observations": len(rs)}
    if annualization is not None:
        if annualization <= 0:
            raise ValueError("annualization must be positive")
        out["annualized"] = sqrt(variance * annualization)
    return out
