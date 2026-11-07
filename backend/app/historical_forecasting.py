"""Leakage-aware one-step historical forecasting benchmarks.

This module is for educational research only. It reports holdout forecast
errors; it does not produce investment advice, trade signals, or orders.
"""
from __future__ import annotations

import math
from typing import Sequence


def _finite_number(value) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError):
        return False


def _log_returns(prices: Sequence[float]) -> list[float]:
    if not isinstance(prices, (list, tuple)) or len(prices) < 2:
        raise ValueError("prices must contain at least two values")
    result = []
    for i, price in enumerate(prices):
        if isinstance(price, bool) or not isinstance(price, (int, float)):
            raise ValueError(f"prices[{i}] must be numeric")
        # Very large Python integers can raise OverflowError during float
        # conversion inside math.isfinite; normalize that into our input error.
        try:
            finite = math.isfinite(price)
        except (OverflowError, TypeError):
            finite = False
        if not finite or price <= 0:
            raise ValueError(f"prices[{i}] must be finite and positive")
    for index, (previous, current) in enumerate(zip(prices, prices[1:])):
        # Avoid overflow/underflow in the intermediate current / previous ratio.
        log_return = math.log(current) - math.log(previous)
        if not math.isfinite(log_return):
            raise ValueError(f"log return at index {index} must be finite")
        result.append(log_return)
    return result


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting for small ridge systems."""
    n = len(vector)
    if n == 0 or len(matrix) != n or any(len(row) != n for row in matrix):
        raise ValueError("regression system must be a non-empty square matrix")
    for row_index, row in enumerate(matrix):
        for col_index, value in enumerate(row):
            if isinstance(value, bool) or not _finite_number(value):
                raise ValueError(f"matrix[{row_index}][{col_index}] must be finite numeric")
    for index, value in enumerate(vector):
        if not _finite_number(value):
            raise ValueError(f"vector[{index}] must be finite numeric")
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
    solution = [augmented[i][-1] for i in range(n)]
    if not all(_finite_number(value) for value in solution):
        raise ValueError("regression coefficients must be finite")
    return solution


def _fit_ridge(features: list[list[float]], targets: list[float], alpha: float) -> list[float]:
    if not features or len(features) != len(targets):
        raise ValueError("features and targets must be non-empty and aligned")
    width = len(features[0])
    if width == 0 or any(len(row) != width for row in features):
        raise ValueError("feature rows must have a consistent non-zero width")
    if isinstance(alpha, bool) or not _finite_number(alpha) or alpha <= 0:
        raise ValueError("ridge alpha must be finite and positive")
    for row_index, row in enumerate(features):
        for column_index, value in enumerate(row):
            if not _finite_number(value):
                raise ValueError(f"features[{row_index}][{column_index}] must be finite numeric")
    for index, value in enumerate(targets):
        if not _finite_number(value):
            raise ValueError(f"targets[{index}] must be finite numeric")
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
    if not coefficients or not features:
        raise ValueError("coefficients and features must be non-empty")
    if any(len(row) != len(coefficients) - 1 for row in features):
        raise ValueError("feature width must match coefficient count")
    if any(not _finite_number(value) for value in coefficients):
        raise ValueError("coefficients must be finite numeric")
    predictions = []
    for row_index, row in enumerate(features):
        if any(not _finite_number(value) for value in row):
            raise ValueError(f"features[{row_index}] must contain finite numeric values")
        try:
            prediction = coefficients[0] + math.fsum(
                weight * value for weight, value in zip(coefficients[1:], row)
            )
        except (OverflowError, ValueError):
            raise ValueError("forecast predictions must be finite") from None
        if not _finite_number(prediction):
            raise ValueError("forecast predictions must be finite")
        predictions.append(prediction)
    return predictions


def _metrics(actual: list[float], predicted: list[float]) -> dict[str, float]:
    """Compute forecast metrics after validating aligned finite observations."""
    if len(actual) != len(predicted):
        raise ValueError("actual and predicted must have equal lengths")
    if not actual:
        raise ValueError("actual and predicted must be non-empty")
    for name, values in (("actual", actual), ("predicted", predicted)):
        for index, value in enumerate(values):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name}[{index}] must be numeric")
            try:
                finite = math.isfinite(value)
            except (OverflowError, TypeError):
                finite = False
            if not finite:
                raise ValueError(f"{name}[{index}] must be finite")

    try:
        errors = [prediction - target for target, prediction in zip(actual, predicted)]
    except (OverflowError, TypeError):
        raise ValueError("forecast errors must be finite") from None
    try:
        errors_finite = all(math.isfinite(error) for error in errors)
    except (OverflowError, TypeError):
        errors_finite = False
    if not errors_finite:
        raise ValueError("forecast errors must be finite")
    # hypot avoids overflow from squaring large, but finite, error values.
    try:
        mae = math.fsum(abs(error) for error in errors) / len(errors)
        rmse = math.hypot(*errors) / math.sqrt(len(errors))
    except (OverflowError, ValueError):
        raise ValueError("forecast metrics must be finite") from None
    if not math.isfinite(mae) or not math.isfinite(rmse):
        raise ValueError("forecast metrics must be finite")
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
    # Fit the constant-mean baseline on the same pre-test history only.
    pretest_targets = targets[:validation_end]
    try:
        mean_return = math.fsum(pretest_targets) / len(pretest_targets)
    except (OverflowError, ValueError):
        raise ValueError("pretest mean return must be finite") from None
    if not math.isfinite(mean_return):
        raise ValueError("pretest mean return must be finite")
    mean_baseline_predictions = [mean_return] * len(test_y)

    model_metrics = _metrics(test_y, model_predictions)
    baseline_metrics = _metrics(test_y, baseline_predictions)
    mean_baseline_metrics = _metrics(test_y, mean_baseline_predictions)

    def _baseline_comparison(model_value: float, baseline_value: float) -> dict:
        # Positive improvement means the model's error is lower than baseline.
        absolute_improvement = baseline_value - model_value
        relative_improvement = (
            absolute_improvement / baseline_value
            if baseline_value > 0 else None
        )
        return {
            "absolute_error_reduction": absolute_improvement,
            "relative_error_reduction": relative_improvement,
        }

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
        "test_model": model_metrics,
        "test_zero_return_baseline": baseline_metrics,
        "pretest_mean_return_baseline": {
            "forecast_log_return": mean_return,
            **mean_baseline_metrics,
            "fit_samples": len(pretest_targets),
        },
        "test_vs_zero_return_baseline": {
            "mae": _baseline_comparison(
                model_metrics["mae_log_return"],
                baseline_metrics["mae_log_return"],
            ),
            "rmse": _baseline_comparison(
                model_metrics["rmse_log_return"],
                baseline_metrics["rmse_log_return"],
            ),
            "interpretation": (
                "Positive error reduction means lower holdout error than the "
                "zero-return baseline; negative means worse. This is descriptive "
                "for this test window only, not evidence of tradable edge."
            ),
        },
        "test_vs_pretest_mean_baseline": {
            "mae": _baseline_comparison(
                model_metrics["mae_log_return"],
                mean_baseline_metrics["mae_log_return"],
            ),
            "rmse": _baseline_comparison(
                model_metrics["rmse_log_return"],
                mean_baseline_metrics["rmse_log_return"],
            ),
            "interpretation": (
                "The constant-mean baseline is estimated using pre-test targets "
                "only; comparison is descriptive for this holdout window."
            ),
        },
        "research_only": True,
        "limitations": [
            "Uses only historical adjusted closing prices and lagged returns.",
            "One symbol and one horizon do not establish generalization.",
            "No transaction costs, slippage, taxes, or portfolio outcomes are modeled.",
            "Forecast metrics are not investment advice or a trading recommendation.",
        ],
    }



def evaluate_walk_forward_return_forecast(
    adjusted_closes: Sequence[float],
    *,
    lookback: int = 5,
    min_history_samples: int = 80,
    test_window: int = 20,
    step_size: int | None = None,
) -> dict:
    """Evaluate expanding-window forecasts over multiple chronological windows.

    Every window's model and constant-mean baseline use only observations
    strictly before that window. Ridge alpha is selected on a validation slice
    within the pre-window history. No test-window values are used for fitting
    or model selection. This is a descriptive research benchmark, not a
    trading strategy or evidence of future profitability.
    """
    if not isinstance(lookback, int) or isinstance(lookback, bool) or not 2 <= lookback <= 20:
        raise ValueError("lookback must be an integer between 2 and 20")
    if not isinstance(min_history_samples, int) or isinstance(min_history_samples, bool) or min_history_samples < 40:
        raise ValueError("min_history_samples must be an integer >= 40")
    if not isinstance(test_window, int) or isinstance(test_window, bool) or test_window < 5:
        raise ValueError("test_window must be an integer >= 5")
    if step_size is None:
        step_size = test_window
    if not isinstance(step_size, int) or isinstance(step_size, bool) or step_size < 1:
        raise ValueError("step_size must be a positive integer")

    returns = _log_returns(adjusted_closes)
    features, targets = [], []
    for target_index in range(lookback, len(returns)):
        features.append(returns[target_index - lookback:target_index])
        targets.append(returns[target_index])

    if step_size < test_window:
        raise ValueError(
            "step_size must be >= test_window to prevent overlapping test windows"
        )
    if len(targets) < min_history_samples + test_window:
        raise ValueError("insufficient history for walk-forward evaluation")

    candidates = (1e-6, 1e-4, 1e-2, 1.0)
    windows = []
    start = min_history_samples
    while start + test_window <= len(targets):
        # start is the first test target. All history ends before start.
        history_x, history_y = features[:start], targets[:start]
        validation_start = int(len(history_y) * 0.85)
        if validation_start < 30 or start - validation_start < 5:
            raise ValueError("insufficient pre-test history for validation")
        train_x, train_y = history_x[:validation_start], history_y[:validation_start]
        val_x, val_y = history_x[validation_start:], history_y[validation_start:]
        validation_scores = []
        for alpha in candidates:
            coefficients = _fit_ridge(train_x, train_y, alpha)
            predictions = _predict(coefficients, val_x)
            try:
                mae = math.fsum(abs(actual - predicted) for actual, predicted in zip(val_y, predictions)) / len(val_y)
            except (OverflowError, ValueError):
                raise ValueError("validation forecast error must be finite") from None
            if not math.isfinite(mae):
                raise ValueError("validation forecast error must be finite")
            validation_scores.append((mae, alpha))
        selected_alpha = min(validation_scores)[1]

        # Refit only on the complete history available before the test window.
        coefficients = _fit_ridge(history_x, history_y, selected_alpha)
        test_x = features[start:start + test_window]
        test_y = targets[start:start + test_window]
        model_predictions = _predict(coefficients, test_x)
        zero_predictions = [0.0] * len(test_y)
        try:
            mean_return = math.fsum(history_y) / len(history_y)
        except (OverflowError, ValueError):
            raise ValueError("pretest mean return must be finite") from None
        if not math.isfinite(mean_return):
            raise ValueError("pretest mean return must be finite")
        mean_predictions = [mean_return] * len(test_y)

        model_metrics = _metrics(test_y, model_predictions)
        zero_metrics = _metrics(test_y, zero_predictions)
        mean_metrics = _metrics(test_y, mean_predictions)
        windows.append({
            "window_index": len(windows) + 1,
            "history_samples": start,
            "validation_samples": len(val_y),
            "test_start_target_index": start,
            "test_end_target_index_exclusive": start + test_window,
            "selected_ridge_alpha": selected_alpha,
            "model": model_metrics,
            "zero_return_baseline": zero_metrics,
            "pretest_mean_return_baseline": {
                "forecast_log_return": mean_return,
                "fit_samples": len(history_y),
                **mean_metrics,
            },
        })
        start += step_size

    def aggregate(metric_key: str, group: str) -> dict:
        values = [window[group][metric_key] for window in windows]
        ordered = sorted(values)
        middle = len(ordered) // 2
        median = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
        try:
            mean = math.fsum(values) / len(values)
        except (OverflowError, ValueError):
            raise ValueError("aggregate forecast metrics must be finite") from None
        if not math.isfinite(mean) or not math.isfinite(median):
            raise ValueError("aggregate forecast metrics must be finite")
        return {"mean": mean, "median": median, "window_count": len(values)}

    return {
        "task": "walk_forward_next_day_log_return_forecast",
        "method": "expanding_window_ridge_with_chronological_validation",
        "lookback": lookback,
        "min_history_samples": min_history_samples,
        "test_window_samples": test_window,
        "step_size_samples": step_size,
        "window_count": len(windows),
        "windows": windows,
        "aggregate_test_metrics": {
            group: {
                metric: aggregate(metric, group)
                for metric in ("mae_log_return", "rmse_log_return", "directional_accuracy")
            }
            for group in ("model", "zero_return_baseline", "pretest_mean_return_baseline")
        },
        "research_only": True,
        "limitations": [
            "Expanding windows reuse overlapping history; window scores are not independent.",
            "Results depend on symbol, provider, date range, and market regime.",
            "This evaluates forecast error only, not profitability or execution outcomes.",
            "No transaction costs, slippage, taxes, or portfolio outcomes are modeled.",
            "Synthetic test fixtures validate code mechanics, not predictive skill.",
        ],
    }

def evaluate_walk_forward_forecast(
    adjusted_closes: Sequence[float], *, lookback: int = 5,
    min_train_samples: int = 100, test_window_size: int = 20,
    step_size: int | None = None,
) -> dict:
    """Evaluate repeated expanding-window forecasts without future leakage.

    Each window's validation segment is the final 20% of its pre-test history.
    Alpha is selected on that segment, then the model and mean baseline are
    refit using all pre-test observations. Test windows are never used for
    fitting or hyperparameter selection. Indices refer to generated return
    samples (not calendar dates).
    """
    if not isinstance(lookback, int) or isinstance(lookback, bool) or not 2 <= lookback <= 20:
        raise ValueError("lookback must be an integer between 2 and 20")
    for name, value, minimum in (
        ("min_train_samples", min_train_samples, 80),
        ("test_window_size", test_window_size, 5),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
            raise ValueError(f"{name} must be an integer >= {minimum}")
    if step_size is None:
        step_size = test_window_size
    if not isinstance(step_size, int) or isinstance(step_size, bool) or step_size < 1:
        raise ValueError("step_size must be a positive integer")

    if step_size < test_window_size:
        raise ValueError(
            "step_size must be >= test_window_size to prevent overlapping test windows"
        )

    returns = _log_returns(adjusted_closes)
    features, targets = [], []
    for target_index in range(lookback, len(returns)):
        features.append(returns[target_index - lookback:target_index])
        targets.append(returns[target_index])

    if len(targets) < min_train_samples + test_window_size:
        raise ValueError("insufficient history for requested walk-forward windows")

    candidates = (1e-6, 1e-4, 1e-2, 1.0)
    windows = []
    cursor = min_train_samples
    while cursor + test_window_size <= len(targets):
        pretest_x, pretest_y = features[:cursor], targets[:cursor]
        validation_start = int(cursor * 0.80)
        if validation_start < 50 or cursor - validation_start < 10:
            raise ValueError("insufficient pre-test history for validation split")
        train_x, train_y = pretest_x[:validation_start], pretest_y[:validation_start]
        val_x, val_y = pretest_x[validation_start:], pretest_y[validation_start:]
        validation_scores = []
        for alpha in candidates:
            coefficients = _fit_ridge(train_x, train_y, alpha)
            predictions = _predict(coefficients, val_x)
            try:
                score = math.fsum(abs(a - p) for a, p in zip(val_y, predictions)) / len(val_y)
            except (OverflowError, ValueError):
                raise ValueError("validation forecast error must be finite") from None
            if not math.isfinite(score):
                raise ValueError("validation forecast error must be finite")
            validation_scores.append((score, alpha))
        selected_alpha = min(validation_scores)[1]

        coefficients = _fit_ridge(pretest_x, pretest_y, selected_alpha)
        test_x = features[cursor:cursor + test_window_size]
        test_y = targets[cursor:cursor + test_window_size]
        model_metrics = _metrics(test_y, _predict(coefficients, test_x))
        zero_metrics = _metrics(test_y, [0.0] * len(test_y))
        try:
            mean_return = math.fsum(pretest_y) / len(pretest_y)
        except (OverflowError, ValueError):
            raise ValueError("pretest mean return must be finite") from None
        if not math.isfinite(mean_return):
            raise ValueError("pretest mean return must be finite")
        mean_metrics = _metrics(test_y, [mean_return] * len(test_y))
        windows.append({
            "window_number": len(windows) + 1,
            "pretest_samples": cursor,
            "validation_samples": len(val_y),
            "test_sample_start_index": cursor,
            "test_sample_end_index_exclusive": cursor + test_window_size,
            "selected_ridge_alpha": selected_alpha,
            "model": model_metrics,
            "zero_return_baseline": zero_metrics,
            "pretest_mean_return_baseline": {
                "forecast_log_return": mean_return,
                "fit_samples": len(pretest_y),
                **mean_metrics,
            },
        })
        cursor += step_size

    def average_metric(rows: list[dict], key: str) -> float:
        try:
            value = math.fsum(row[key] for row in rows) / len(rows)
        except (OverflowError, ValueError):
            raise ValueError("aggregate forecast metrics must be finite") from None
        if not math.isfinite(value):
            raise ValueError("aggregate forecast metrics must be finite")
        return value

    aggregate_model = {
        key: average_metric([row["model"] for row in windows], key)
        for key in ("mae_log_return", "rmse_log_return", "directional_accuracy")
    }
    aggregate_zero = {
        key: average_metric([row["zero_return_baseline"] for row in windows], key)
        for key in ("mae_log_return", "rmse_log_return", "directional_accuracy")
    }
    aggregate_mean = {
        key: average_metric([row["pretest_mean_return_baseline"] for row in windows], key)
        for key in ("mae_log_return", "rmse_log_return", "directional_accuracy")
    }
    return {
        "task": "expanding_walk_forward_next_day_log_return_forecast",
        "method": "ridge_regression_on_lagged_log_returns",
        "lookback": lookback,
        "window_count": len(windows),
        "test_window_size": test_window_size,
        "step_size": step_size,
        "initial_pretest_samples": min_train_samples,
        "aggregate_mean_window_metrics": {
            "model": aggregate_model,
            "zero_return_baseline": aggregate_zero,
            "pretest_mean_return_baseline": aggregate_mean,
        },
        "mean_window_error_reduction_vs_zero_baseline": {
            metric: aggregate_zero[metric] - aggregate_model[metric]
            for metric in ("mae_log_return", "rmse_log_return")
        },
        "mean_window_error_reduction_vs_pretest_mean_baseline": {
            metric: aggregate_mean[metric] - aggregate_model[metric]
            for metric in ("mae_log_return", "rmse_log_return")
        },
        "windows": windows,
        "research_only": True,
        "limitations": [
            "Window metrics are arithmetic means of per-window metrics, not pooled observation metrics.",
            "Test windows are non-overlapping; expanding pre-test histories still reuse prior observations.",
            "Indices identify return samples, not dates; calendar timestamps are not included.",
            "A small single-symbol synthetic or historical run does not establish generalization or tradable edge.",
            "No transaction costs, slippage, taxes, portfolio outcomes, or investment advice.",
        ],
    }

