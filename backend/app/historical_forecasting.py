"""Leakage-aware one-step historical forecasting benchmarks.

This module is for educational research only. It reports holdout forecast
errors; it does not produce investment advice, trade signals, or orders.
"""
from __future__ import annotations

import math
from typing import Sequence


def _log_returns(prices: Sequence[float]) -> list[float]:
    if not isinstance(prices, (list, tuple)) or len(prices) < 2:
        raise ValueError("prices must contain at least two values")
    result = []
    for i, price in enumerate(prices):
        if isinstance(price, bool) or not isinstance(price, (int, float)):
            raise ValueError(f"prices[{i}] must be numeric")
        if not math.isfinite(price) or price <= 0:
            raise ValueError(f"prices[{i}] must be finite and positive")
    for previous, current in zip(prices, prices[1:]):
        result.append(math.log(current / previous))
    return result


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting for small ridge systems."""
    n = len(vector)
    augmented = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(augmented[row][col]))
        if abs(augmented[pivot][col]) < 1e-12:
            raise ValueError("singular regression system")
        augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        divisor = augmented[col][col]
        augmented[col] = [value / divisor for value in augmented[col]]
        for row in range(n):
            if row == col:
                continue
            factor = augmented[row][col]
            augmented[row] = [
                value - factor * pivot_value
                for value, pivot_value in zip(augmented[row], augmented[col])
            ]
    return [augmented[i][-1] for i in range(n)]


def _fit_ridge(features: list[list[float]], targets: list[float], alpha: float) -> list[float]:
    width = len(features[0])
    # Add an intercept; do not penalize the intercept term.
    design = [[1.0] + row for row in features]
    size = width + 1
    gram = [[0.0] * size for _ in range(size)]
    rhs = [0.0] * size
    for row, target in zip(design, targets):
        for i in range(size):
            rhs[i] += row[i] * target
            for j in range(size):
                gram[i][j] += row[i] * row[j]
    for i in range(1, size):
        gram[i][i] += alpha
    return _solve_linear_system(gram, rhs)


def _predict(coefficients: list[float], features: list[list[float]]) -> list[float]:
    return [
        coefficients[0] + sum(weight * value for weight, value in zip(coefficients[1:], row))
        for row in features
    ]


def _metrics(actual: list[float], predicted: list[float]) -> dict[str, float]:
    errors = [prediction - target for target, prediction in zip(actual, predicted)]
    mae = sum(abs(error) for error in errors) / len(errors)
    rmse = math.sqrt(sum(error * error for error in errors) / len(errors))
    directional = sum(
        (target > 0 and prediction > 0) or (target < 0 and prediction < 0)
        or (target == 0 and prediction == 0)
        for target, prediction in zip(actual, predicted)
    ) / len(actual)
    return {
        "sample_count": len(actual),
        "mae_log_return": mae,
        "rmse_log_return": rmse,
        "directional_accuracy": directional,
    }


def evaluate_next_day_return_forecast(
    adjusted_closes: Sequence[float], *, lookback: int = 5
) -> dict:
    """Train a tiny ridge regression on lagged returns and evaluate holdout.

    Chronological split: first 70% train, next 15% validation, final 15% test.
    Validation selects ridge alpha; model is then refit on train+validation.
    Only the final test segment is reported as out-of-sample performance.
    A zero-return forecast is the baseline. The data is not shuffled.
    """
    if not isinstance(lookback, int) or isinstance(lookback, bool) or not 2 <= lookback <= 20:
        raise ValueError("lookback must be an integer between 2 and 20")
    returns = _log_returns(adjusted_closes)
    features, targets = [], []
    for target_index in range(lookback, len(returns)):
        features.append(returns[target_index - lookback:target_index])
        targets.append(returns[target_index])

    n = len(targets)
    train_end = int(n * 0.70)
    validation_end = int(n * 0.85)
    if train_end < lookback + 5 or validation_end <= train_end or n - validation_end < 10:
        raise ValueError("insufficient history: need at least 100 valid daily closes")

    train_x, train_y = features[:train_end], targets[:train_end]
    val_x, val_y = features[train_end:validation_end], targets[train_end:validation_end]
    test_x, test_y = features[validation_end:], targets[validation_end:]

    candidates = (1e-6, 1e-4, 1e-2, 1.0)
    validation_scores = []
    for alpha in candidates:
        coefficients = _fit_ridge(train_x, train_y, alpha)
        val_predictions = _predict(coefficients, val_x)
        val_mae = sum(abs(a - p) for a, p in zip(val_y, val_predictions)) / len(val_y)
        validation_scores.append((val_mae, alpha))
    selected_alpha = min(validation_scores)[1]

    final_coefficients = _fit_ridge(
        features[:validation_end], targets[:validation_end], selected_alpha
    )
    model_predictions = _predict(final_coefficients, test_x)
    baseline_predictions = [0.0] * len(test_y)

    return {
        "task": "next_day_log_return_forecast",
        "method": "ridge_regression_on_lagged_log_returns",
        "lookback": lookback,
        "split": {
            "train_samples": train_end,
            "validation_samples": validation_end - train_end,
            "test_samples": n - validation_end,
            "shuffle": False,
        },
        "selected_ridge_alpha": selected_alpha,
        "validation_mae_by_alpha": [
            {"alpha": alpha, "mae_log_return": score}
            for score, alpha in sorted(validation_scores)
        ],
        "test_model": _metrics(test_y, model_predictions),
        "test_zero_return_baseline": _metrics(test_y, baseline_predictions),
        "research_only": True,
        "limitations": [
            "Uses only historical adjusted closing prices and lagged returns.",
            "One symbol and one horizon do not establish generalization.",
            "No transaction costs, slippage, taxes, or portfolio outcomes are modeled.",
            "Forecast metrics are not investment advice or a trading recommendation.",
        ],
    }
