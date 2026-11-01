"""Evidence-first deterministic research orchestration foundation.

This module combines structured findings from existing analytical workers.
It does not invoke an LLM, fetch market data, predict prices, or emit trades.
"""
from collections import defaultdict
from math import isfinite

MARKETS = ("india", "us", "crypto", "forex")
QUALITY = ("verified_by_importer", "partial", "unverified", "synthetic")
QUALITY_RANK = {"verified_by_importer": 3, "partial": 2, "unverified": 1, "synthetic": 0}


def build_research_brief(findings, requested_markets=None):
    """Validate, group and qualify worker findings without inventing conclusions."""
    if not isinstance(findings, list) or len(findings) > 1000:
        raise ValueError("findings must be a list containing at most 1000 records")
    requested = list(MARKETS if requested_markets is None else requested_markets)
    if not requested or len(set(requested)) != len(requested) or any(x not in MARKETS for x in requested):
        raise ValueError("requested_markets must contain unique supported market groups")

    grouped = defaultdict(dict)
    market_counts = {market: 0 for market in requested}
    quality_counts = {label: 0 for label in QUALITY}
    accepted = []

    for index, item in enumerate(findings):
        if not isinstance(item, dict):
            raise ValueError(f"finding {index} must be an object")
        market = item.get("market_group")
        if market not in MARKETS:
            raise ValueError(f"finding {index} has an unsupported market_group")
        if market not in requested:
            continue
        topic, key, unit = item.get("topic"), item.get("finding_key"), item.get("unit")
        if not isinstance(topic, str) or not topic.strip() or len(topic) > 80:
            raise ValueError(f"finding {index} requires a topic of 1 to 80 characters")
        if not isinstance(key, str) or not key.strip() or len(key) > 120:
            raise ValueError(f"finding {index} requires a finding_key of 1 to 120 characters")
        if unit is not None and (not isinstance(unit, str) or len(unit) > 40):
            raise ValueError(f"finding {index} unit must be a string of at most 40 characters")
        value = item.get("finding_value")
        if isinstance(value, (dict, list)) or not isinstance(value, (str, int, float, bool, type(None))):
            raise ValueError(f"finding {index} finding_value must be scalar")
        if isinstance(value, float) and not isfinite(value):
            raise ValueError(f"finding {index} finding_value must be finite")
        quality = item.get("quality_status", "unverified")
        if quality not in QUALITY:
            raise ValueError(f"finding {index} has an unsupported quality_status")
        refs = item.get("source_refs", [])
        if not isinstance(refs, list) or len(refs) > 20 or any(not isinstance(ref, str) or not ref.strip() or len(ref) > 300 for ref in refs):
            raise ValueError(f"finding {index} source_refs must contain at most 20 non-empty strings")
        worker = item.get("worker_id", "unspecified")
        if not isinstance(worker, str) or not worker.strip() or len(worker) > 96:
            raise ValueError(f"finding {index} worker_id must be a non-empty string of at most 96 characters")

        group = (topic.strip(), key.strip(), unit)
        encoded = (type(value).__name__, repr(value))
        record = grouped[group].setdefault(encoded, {
            "value": value, "market_groups": [], "worker_ids": [],
            "source_refs": [], "quality_labels": [], "finding_count": 0,
        })
        record["finding_count"] += 1
        if market not in record["market_groups"]:
            record["market_groups"].append(market)
        if worker not in record["worker_ids"]:
            record["worker_ids"].append(worker)
        for ref in refs:
            if ref not in record["source_refs"]:
                record["source_refs"].append(ref)
        if quality not in record["quality_labels"]:
            record["quality_labels"].append(quality)
        market_counts[market] += 1
        quality_counts[quality] += 1
        accepted.append(item)

    comparisons = []
    for (topic, key, unit), values in sorted(grouped.items()):
        groups = list(values.values())
        participating = sorted({m for group in groups for m in group["market_groups"]})
        comparisons.append({
            "topic": topic, "finding_key": key, "unit": unit,
            "distinct_value_count": len(groups),
            "cross_market_comparable": len(participating) > 1,
            "market_groups": participating,
            "values": groups,
            "status": "disagreement_requires_review" if len(groups) > 1 else "single_observed_value",
        })

    represented = [market for market, count in market_counts.items() if count]
    all_sources = sorted({ref for item in accepted for ref in item.get("source_refs", [])})
    verified_count = quality_counts["verified_by_importer"]
    non_synthetic_count = sum(quality_counts[q] for q in ("verified_by_importer", "partial", "unverified"))
    return {
        "mode": "deterministic_evidence_aggregation",
        "findings_received": len(findings),
        "findings_accepted": len(accepted),
        "requested_market_groups": requested,
        "represented_market_groups": represented,
        "missing_market_groups": [m for m in requested if market_counts[m] == 0],
        "market_finding_counts": market_counts,
        "quality_counts": quality_counts,
        "verified_by_importer_findings": verified_count,
        "source_refs": all_sources,
        "comparisons": comparisons,
        "evidence_status": (
            "no_findings" if not accepted else
            "synthetic_only" if non_synthetic_count == 0 else
            "mixed_quality" if quality_counts["synthetic"] or quality_counts["unverified"] or quality_counts["partial"] else
            "importer_verified"
        ),
        "limitations": [
            "This is deterministic aggregation, not LLM reasoning or autonomous worker execution.",
            "Importer quality labels are metadata and are not independently authenticated here.",
            "Different values may use different instruments, windows, sessions or methodologies.",
            "A missing market means no finding was supplied; it does not mean zero activity.",
            "No live data fetch, forecast, investment recommendation or order execution occurs.",
        ],
    }
