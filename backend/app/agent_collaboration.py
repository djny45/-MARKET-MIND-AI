"""Deterministic cross-market collaboration briefs.

The brief assembles caller-supplied agent notes into a reviewable roundtable.
It does not infer causality, decide which market leads, or generate trade signals.
"""
import json

MARKET_GROUPS = ("india", "us", "crypto", "forex")
QUALITY_LABELS = ("verified_by_importer", "partial", "unverified", "synthetic")


def build_collaboration_brief(messages):
    if not isinstance(messages, list):
        raise ValueError("messages must be a list")

    market_counts = {market: 0 for market in MARKET_GROUPS}
    quality_counts = {label: 0 for label in QUALITY_LABELS}
    topic_counts = {}
    findings = {}

    for message in messages:
        if not isinstance(message, dict):
            continue
        market = message.get("market_group")
        if market not in MARKET_GROUPS:
            continue
        market_counts[market] += 1
        quality = message.get("quality_status", "unverified")
        if quality not in quality_counts:
            quality = "unverified"
        quality_counts[quality] += 1

        topic = message.get("topic", "research_note")
        topic_counts[topic] = topic_counts.get(topic, 0) + 1
        payload = message.get("payload")
        if not isinstance(payload, dict):
            continue
        key = payload.get("finding_key")
        value = payload.get("finding_value")
        unit = payload.get("unit")
        if not isinstance(key, str) or not key.strip() or len(key) > 120:
            continue
        if isinstance(value, (dict, list)) or not isinstance(value, (str, int, float, bool, type(None))):
            continue
        if isinstance(value, float) and (value != value or abs(value) == float("inf")):
            continue
        group_key = (topic, key.strip(), unit if isinstance(unit, str) else None)
        encoded_value = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        bucket = findings.setdefault(group_key, {})
        record = bucket.setdefault(encoded_value, {
            "value": value, "message_count": 0, "market_groups": [],
            "agent_ids": [], "quality_labels": [],
        })
        record["message_count"] += 1
        if market not in record["market_groups"]:
            record["market_groups"].append(market)
        agent_id = message.get("agent_id")
        if isinstance(agent_id, str) and agent_id not in record["agent_ids"]:
            record["agent_ids"].append(agent_id)
        if quality not in record["quality_labels"]:
            record["quality_labels"].append(quality)

    comparisons = []
    for (topic, key, unit), value_groups in sorted(findings.items()):
        groups = list(value_groups.values())
        markets = sorted({market for item in groups for market in item["market_groups"]})
        comparisons.append({
            "topic": topic,
            "finding_key": key,
            "unit": unit,
            "matching_value_groups": len(groups),
            "cross_market_comparable": len(markets) > 1,
            "values": groups,
            "interpretation": (
                "Different supplied values require analyst review; instruments, windows, "
                "units and methodologies may not be directly comparable."
                if len(groups) > 1 else
                "Matching supplied values are descriptive agreement only, not proof of causality or consensus."
            ),
        })

    participating = [market for market, count in market_counts.items() if count]
    return {
        "network": "four_market_mesh",
        "messages_reviewed": len(messages),
        "participating_market_groups": participating,
        "market_message_counts": market_counts,
        "quality_label_counts": quality_counts,
        "topic_message_counts": dict(sorted(topic_counts.items())),
        "cross_market_context_available": len(participating) > 1,
        "finding_comparisons": comparisons,
        "limitations": [
            "The brief summarizes caller-supplied messages; it does not run independent AI agents.",
            "Quality labels and source references are not independently authenticated.",
            "Matching values do not establish causality, predictive power or statistical consensus.",
            "Different values may reflect different instruments, units, windows, sessions or methods.",
            "No live feeds, trading signals, broker connections or order execution are used.",
        ],
    }
