"""Chronological split utilities for leakage-aware research evaluation.

This module only validates time-series evaluation boundaries. It does not train
models, generate signals, or connect to trading/execution services.
"""
from datetime import datetime, timezone
from typing import Any


def _parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty ISO-8601 timestamp string")
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def validate_chronological_splits(
    train_end: str,
    validation_start: str,
    validation_end: str,
    test_start: str,
    *,
    embargo_seconds: int = 0,
) -> dict[str, Any]:
    """Validate ordered split boundaries and a configurable embargo.

    Boundary timestamps are treated as the last timestamp in each preceding
    split and the first timestamp in the next split. The gaps must be at least
    embargo_seconds. The function validates boundaries only; it cannot inspect
    feature windows or prove that upstream data has no leakage.
    """
    if not isinstance(embargo_seconds, int) or isinstance(embargo_seconds, bool) or embargo_seconds < 0:
        raise ValueError("embargo_seconds must be a non-negative integer")

    train = _parse_timestamp(train_end, "train_end")
    val_start = _parse_timestamp(validation_start, "validation_start")
    val_end = _parse_timestamp(validation_end, "validation_end")
    test = _parse_timestamp(test_start, "test_start")

    # Normalize to UTC for comparisons without relying on local timezone.
    train, val_start, val_end, test = (
        item.astimezone(timezone.utc) for item in (train, val_start, val_end, test)
    )
    embargo = (val_start - train).total_seconds()
    test_embargo = (test - val_end).total_seconds()

    if val_start <= train:
        raise ValueError("validation_start must be after train_end")
    if val_end < val_start:
        raise ValueError("validation_end must be on or after validation_start")
    if test <= val_end:
        raise ValueError("test_start must be after validation_end")
    if embargo < embargo_seconds:
        raise ValueError("train/validation boundary does not satisfy embargo_seconds")
    if test_embargo < embargo_seconds:
        raise ValueError("validation/test boundary does not satisfy embargo_seconds")

    return {
        "valid": True,
        "method": "chronological",
        "timezone_normalized": "UTC",
        "embargo_seconds": embargo_seconds,
        "train_end": train.isoformat(),
        "validation_start": val_start.isoformat(),
        "validation_end": val_end.isoformat(),
        "test_start": test.isoformat(),
        "train_validation_gap_seconds": embargo,
        "validation_test_gap_seconds": test_embargo,
        "random_shuffling_allowed": False,
        "research_only": True,
    }



def validate_dataset_manifest(manifest: Any) -> dict[str, Any]:
    """Validate metadata required before a historical dataset can be evaluated.

    This is a metadata gate, not a data inspection or performance evaluation.
    It cannot verify the underlying bars, corporate actions, feature leakage,
    or provider claims.
    """
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a dictionary")

    required_text = ("dataset_id", "source", "symbol", "timeframe")
    normalized: dict[str, Any] = {}
    for field in required_text:
        value = manifest.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")
        normalized[field] = value.strip()

    start = _parse_timestamp(manifest.get("start"), "start")
    end = _parse_timestamp(manifest.get("end"), "end")
    start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    if end <= start:
        raise ValueError("end must be after start")

    sample_count = manifest.get("sample_count")
    if not isinstance(sample_count, int) or isinstance(sample_count, bool) or sample_count <= 0:
        raise ValueError("sample_count must be a positive integer")

    missing_fraction = manifest.get("missing_fraction")
    if (
        not isinstance(missing_fraction, (int, float))
        or isinstance(missing_fraction, bool)
        or not 0 <= missing_fraction <= 1
    ):
        raise ValueError("missing_fraction must be a number between 0 and 1")

    synthetic = manifest.get("synthetic")
    if not isinstance(synthetic, bool):
        raise ValueError("synthetic must be a boolean")

    normalized.update({
        "start": start.isoformat(),
        "end": end.isoformat(),
        "sample_count": sample_count,
        "missing_fraction": float(missing_fraction),
        "synthetic": synthetic,
        "metadata_valid": True,
        "evaluation_ready": not synthetic and missing_fraction == 0,
        "research_only": True,
        "limitations": [
            "Metadata validation does not inspect underlying records.",
            "Evaluation readiness is a conservative metadata flag, not proof of data quality or absence of leakage.",
        ],
    })
    return normalized


def evaluate_binary_predictions(actual: Any, predicted: Any) -> dict[str, Any]:
    """Summarize binary research labels against predictions and a majority baseline.

    This computes classification metrics only. It does not convert predictions
    into market signals, returns, portfolio positions, or execution actions.
    """
    if not isinstance(actual, (list, tuple)) or not isinstance(predicted, (list, tuple)):
        raise ValueError("actual and predicted must be lists or tuples")
    if not actual or len(actual) != len(predicted):
        raise ValueError("actual and predicted must be non-empty and have equal length")

    def validate_labels(values: list | tuple, field: str) -> list[int]:
        checked = []
        for index, value in enumerate(values):
            if isinstance(value, bool) or value not in (0, 1):
                raise ValueError(f"{field}[{index}] must be binary label 0 or 1")
            checked.append(int(value))
        return checked

    y_true = validate_labels(actual, "actual")
    y_pred = validate_labels(predicted, "predicted")
    tp = sum(t == 1 and p == 1 for t, p in zip(y_true, y_pred))
    tn = sum(t == 0 and p == 0 for t, p in zip(y_true, y_pred))
    fp = sum(t == 0 and p == 1 for t, p in zip(y_true, y_pred))
    fn = sum(t == 1 and p == 0 for t, p in zip(y_true, y_pred))
    total = len(y_true)
    positives = sum(y_true)
    negatives = total - positives
    accuracy = (tp + tn) / total
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    majority_baseline = max(positives, negatives) / total
    specificity = tn / (tn + fp) if tn + fp else 0.0
    balanced_accuracy = (recall + specificity) / 2
    prevalence = positives / total
    predicted_positive_fraction = sum(y_pred) / total

    return {
        "sample_count": total,
        "confusion_matrix": {"true_positive": tp, "true_negative": tn, "false_positive": fp, "false_negative": fn},
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "balanced_accuracy": balanced_accuracy,
        "positive_label_prevalence": prevalence,
        "predicted_positive_fraction": predicted_positive_fraction,
        "f1": f1,
        "majority_class_baseline_accuracy": majority_baseline,
        "accuracy_delta_vs_majority_baseline": accuracy - majority_baseline,
        "research_only": True,
        "limitations": [
            "Metrics depend on labels and predictions supplied by the caller.",
            "No temporal leakage, class imbalance impact, data provenance, or deployment performance is assessed here.",
            "This output is not a trading signal or a recommendation.",
        ],
    }

def aggregate_binary_evaluation_runs(actual_runs: Any, predicted_runs: Any) -> dict[str, Any]:
    """Aggregate independent binary evaluation splits without hiding fold variance.

    Returns per-split metrics, pooled metrics (computed from concatenated
    predictions), and unweighted mean/standard deviation across splits.
    Callers remain responsible for ensuring splits are chronological,
    non-overlapping, and generated without leakage.
    """
    if not isinstance(actual_runs, (list, tuple)) or not isinstance(predicted_runs, (list, tuple)):
        raise ValueError("actual_runs and predicted_runs must be lists or tuples")
    if not actual_runs or len(actual_runs) != len(predicted_runs):
        raise ValueError("actual_runs and predicted_runs must be non-empty and have equal length")

    fold_results = []
    pooled_actual: list[int] = []
    pooled_predicted: list[int] = []
    for index, (actual, predicted) in enumerate(zip(actual_runs, predicted_runs)):
        try:
            result = evaluate_binary_predictions(actual, predicted)
        except ValueError as exc:
            raise ValueError(f"split {index}: {exc}") from exc
        fold_results.append(result)
        pooled_actual.extend(actual)
        pooled_predicted.extend(predicted)

    metric_names = (
        "accuracy", "precision", "recall", "specificity",
        "balanced_accuracy", "f1",
    )
    means = {
        name: sum(result[name] for result in fold_results) / len(fold_results)
        for name in metric_names
    }
    standard_deviations = {
        name: (
            sum((result[name] - means[name]) ** 2 for result in fold_results)
            / len(fold_results)
        ) ** 0.5
        for name in metric_names
    }

    return {
        "split_count": len(fold_results),
        "per_split": fold_results,
        "unweighted_split_mean": means,
        "unweighted_split_population_std": standard_deviations,
        "pooled": evaluate_binary_predictions(pooled_actual, pooled_predicted),
        "research_only": True,
        "limitations": [
            "Split metrics are unweighted; each split contributes equally regardless of sample count.",
            "Pooled metrics combine all supplied labels and predictions and may obscure split-to-split variation.",
            "The caller must ensure chronological ordering, non-overlap, embargo, and leakage controls.",
            "This summary does not establish out-of-sample profitability or trading performance.",
        ],
    }

def build_binary_research_report(
    manifest: Any,
    split_boundaries: Any,
    actual_runs: Any,
    predicted_runs: Any,
    *,
    embargo_seconds: int = 0,
) -> dict[str, Any]:
    """Build a guarded report from manifest, chronology, and supplied labels.

    This is a reporting/validation helper. It does not load market data,
    generate labels, train a model, or establish predictive or trading value.
    """
    normalized_manifest = validate_dataset_manifest(manifest)
    if not normalized_manifest["evaluation_ready"]:
        raise ValueError(
            "dataset manifest is not evaluation-ready: synthetic data or missing records"
        )
    if not isinstance(split_boundaries, dict):
        raise ValueError("split_boundaries must be a dictionary")

    required_boundaries = (
        "train_end", "validation_start", "validation_end", "test_start"
    )
    missing = [field for field in required_boundaries if field not in split_boundaries]
    if missing:
        raise ValueError(f"split_boundaries missing required fields: {', '.join(missing)}")

    chronology = validate_chronological_splits(
        split_boundaries["train_end"],
        split_boundaries["validation_start"],
        split_boundaries["validation_end"],
        split_boundaries["test_start"],
        embargo_seconds=embargo_seconds,
    )

    # Ensure the declared evaluation window belongs to the declared dataset.
    # Otherwise valid-looking split boundaries can silently refer to data
    # outside the manifest's advertised coverage.
    dataset_start = _parse_timestamp(normalized_manifest["start"], "dataset.start").astimezone(timezone.utc)
    dataset_end = _parse_timestamp(normalized_manifest["end"], "dataset.end").astimezone(timezone.utc)
    split_start = _parse_timestamp(split_boundaries["train_end"], "train_end").astimezone(timezone.utc)
    split_end = _parse_timestamp(split_boundaries["test_start"], "test_start").astimezone(timezone.utc)
    if split_start < dataset_start or split_end > dataset_end:
        raise ValueError("split boundaries must fall within the dataset manifest date range")

    aggregate = aggregate_binary_evaluation_runs(actual_runs, predicted_runs)
    evaluated_samples = aggregate["pooled"]["sample_count"]
    if evaluated_samples > normalized_manifest["sample_count"]:
        raise ValueError(
            "evaluated sample count cannot exceed manifest sample_count"
        )

    return {
        "report_type": "binary_classification_research",
        "dataset": normalized_manifest,
        "chronology": chronology,
        "metrics": aggregate,
        "evaluated_sample_count": evaluated_samples,
        "research_only": True,
        "limitations": [
            "The caller supplies labels and predictions; this helper does not inspect raw market records.",
            "Manifest sample_count is a metadata assertion, not independently verified.",
            "A single set of split boundaries validates chronology only; it does not prove every fold is non-overlapping.",
            "No profitability, risk-adjusted return, or live trading claim is made.",
        ],
    }

