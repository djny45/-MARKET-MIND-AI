"""Chronological, source-isolated dataset manifests with explicit embargo gaps."""
import hashlib
import json
import math
from datetime import datetime, timezone


def _parse_instant(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _canonical_digest(source, bars):
    payload = {
        "source": source,
        "bars": [
            {
                key: bar.get(key)
                for key in (
                    "timestamp", "open", "high", "low", "close",
                    "volume", "status", "source", "retrieved_at",
                )
            }
            for bar in bars
        ],
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _valid_bar(bar):
    for field in ("open", "high", "low", "close", "volume"):
        try:
            value = float(bar[field])
        except (KeyError, TypeError, ValueError, OverflowError):
            return False, f"invalid_{field}"
        if not math.isfinite(value):
            return False, f"non_finite_{field}"
    return True, None


def build_evaluation_manifest(
    history, train_ratio=0.60, validation_ratio=0.20, embargo_bars=1
):
    """Create non-overlapping chronological partitions; no model is trained."""
    if (
        not isinstance(train_ratio, (int, float)) or isinstance(train_ratio, bool)
        or not math.isfinite(train_ratio) or not 0.1 <= train_ratio <= 0.8
    ):
        raise ValueError("train_ratio must be finite and between 0.1 and 0.8")
    if (
        not isinstance(validation_ratio, (int, float)) or isinstance(validation_ratio, bool)
        or not math.isfinite(validation_ratio) or not 0.1 <= validation_ratio <= 0.5
    ):
        raise ValueError("validation_ratio must be finite and between 0.1 and 0.5")
    if train_ratio + validation_ratio >= 0.95:
        raise ValueError("train_ratio plus validation_ratio must be below 0.95")
    if (
        not isinstance(embargo_bars, int) or isinstance(embargo_bars, bool)
        or not 0 <= embargo_bars <= 100
    ):
        raise ValueError("embargo_bars must be an integer between 0 and 100")

    bars = history.get("bars", [])
    if not isinstance(bars, list) or len(bars) > 5000:
        raise ValueError("history must contain a list of at most 5000 bars")

    grouped = {}
    for original_index, bar in enumerate(bars):
        if not isinstance(bar, dict):
            raise ValueError(f"bar {original_index} must be an object")
        source = str(bar.get("source") or "unknown")
        grouped.setdefault(source, []).append((original_index, bar))

    source_manifests = {}
    total_valid = 0
    for source, indexed in sorted(grouped.items()):
        parsed = []
        invalid = []
        for original_index, bar in indexed:
            instant = _parse_instant(bar.get("timestamp"))
            valid, reason = _valid_bar(bar)
            if instant is None:
                invalid.append({"bar_index": original_index, "reason": "invalid_timezone_aware_timestamp"})
            elif not valid:
                invalid.append({"bar_index": original_index, "reason": reason})
            else:
                parsed.append((instant, original_index, bar))

        if invalid:
            source_manifests[source] = {
                "status": "blocked_invalid_observations",
                "observation_count": len(indexed),
                "invalid_observation_count": len(invalid),
                "invalid_observations": invalid[:50],
                "dataset_sha256": None,
                "partitions": {},
                "embargo": [],
            }
            continue

        parsed.sort(key=lambda item: item[0])
        instants = [item[0] for item in parsed]
        duplicates = [
            {"timestamp_utc": instants[i].isoformat(), "first_sorted_index": i - 1}
            for i in range(1, len(instants)) if instants[i] == instants[i - 1]
        ]
        if duplicates:
            source_manifests[source] = {
                "status": "blocked_duplicate_timestamps",
                "observation_count": len(indexed),
                "duplicate_count": len(duplicates),
                "duplicates": duplicates[:50],
                "dataset_sha256": None,
                "partitions": {},
                "embargo": [],
            }
            continue

        chronological_bars = [item[2] for item in parsed]
        digest = _canonical_digest(source, chronological_bars)
        count = len(parsed)
        if count < 10:
            source_manifests[source] = {
                "status": "insufficient_history",
                "observation_count": count,
                "minimum_required": 10,
                "dataset_sha256": digest,
                "partitions": {},
                "embargo": [],
            }
            continue

        first_boundary = int(count * train_ratio)
        second_boundary = int(count * (train_ratio + validation_ratio))
        train_end = first_boundary
        validation_start = min(count, first_boundary + embargo_bars)
        validation_end = second_boundary
        holdout_start = min(count, second_boundary + embargo_bars)

        slices = {
            "development": (0, train_end),
            "validation": (validation_start, validation_end),
            "holdout": (holdout_start, count),
        }
        if any(start >= end for start, end in slices.values()):
            source_manifests[source] = {
                "status": "insufficient_history_for_embargo",
                "observation_count": count,
                "dataset_sha256": digest,
                "partitions": {},
                "embargo": [],
            }
            continue

        partitions = {}
        for name, (start, end) in slices.items():
            segment = parsed[start:end]
            partitions[name] = {
                "observation_count": len(segment),
                "first_timestamp_utc": segment[0][0].isoformat(),
                "last_timestamp_utc": segment[-1][0].isoformat(),
                "first_original_bar_index": segment[0][1],
                "last_original_bar_index": segment[-1][1],
            }
            total_valid += len(segment)

        embargo = []
        if validation_start > first_boundary:
            embargo.append({
                "between": ["development", "validation"],
                "observation_count": validation_start - first_boundary,
                "first_timestamp_utc": parsed[first_boundary][0].isoformat(),
                "last_timestamp_utc": parsed[validation_start - 1][0].isoformat(),
            })
        if holdout_start > second_boundary:
            embargo.append({
                "between": ["validation", "holdout"],
                "observation_count": holdout_start - second_boundary,
                "first_timestamp_utc": parsed[second_boundary][0].isoformat(),
                "last_timestamp_utc": parsed[holdout_start - 1][0].isoformat(),
            })

        source_manifests[source] = {
            "status": "ready",
            "observation_count": count,
            "dataset_sha256": digest,
            "partitions": partitions,
            "embargo": embargo,
            "partition_policy": {
                "train_ratio": train_ratio,
                "validation_ratio": validation_ratio,
                "holdout_ratio": round(1 - train_ratio - validation_ratio, 10),
                "embargo_bars": embargo_bars,
                "method": "chronological_per_source_no_shuffle",
            },
        }

    ready = [item for item in source_manifests.values() if item["status"] == "ready"]
    return {
        "mode": "historical_evaluation_dataset_manifest",
        "symbol": history.get("symbol"),
        "interval": history.get("interval"),
        "source_count": len(grouped),
        "ready_source_count": len(ready),
        "partitioned_observation_count": total_valid,
        "source_manifests": source_manifests,
        "methodology": [
            "Sources are partitioned independently; provider observations are never merged into one chronology.",
            "Partitions are chronological and are not shuffled.",
            "Embargo observations are excluded between development, validation and holdout partitions.",
            "The dataset digest is SHA-256 over canonicalized source and stored OHLCV/provenance fields.",
            "Invalid timestamps, non-finite OHLCV and duplicate source timestamps block that source.",
            "This creates a reproducible partition manifest only; it does not train, tune, backtest or evaluate a model.",
            "Embargo bars reduce direct boundary adjacency but do not by themselves eliminate every form of look-ahead, survivorship, revision or selection bias.",
        ],
        "research_only": True,
    }
