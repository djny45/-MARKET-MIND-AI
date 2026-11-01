"""Evidence-gated cross-market research round assembly.

This module organizes already-published records into a reviewable round. It
does not trigger independent agents, infer causality, or make trade decisions.
"""
from .agent_collaboration import build_collaboration_brief
from .agent_network import MARKET_GROUPS

QUALITY_ORDER = ("verified_by_importer", "partial", "unverified", "synthetic")


def build_research_round(messages, requested_markets=None, min_sources_per_market=1):
    if not isinstance(messages, list) or len(messages) > 2000:
        raise ValueError("messages must be a list containing at most 2000 records")
    requested = list(MARKET_GROUPS if requested_markets is None else requested_markets)
    if not requested or len(set(requested)) != len(requested) or any(m not in MARKET_GROUPS for m in requested):
        raise ValueError("requested_markets must contain unique supported market groups")
    if not isinstance(min_sources_per_market, int) or isinstance(min_sources_per_market, bool) or not 1 <= min_sources_per_market <= 20:
        raise ValueError("min_sources_per_market must be between 1 and 20")

    per_market = {market: {"messages": 0, "source_refs": [], "quality_counts": {q: 0 for q in QUALITY_ORDER}} for market in requested}
    accepted = []
    for item in messages:
        if not isinstance(item, dict) or item.get("market_group") not in requested:
            continue
        market = item["market_group"]
        per_market[market]["messages"] += 1
        quality = item.get("quality_status", "unverified")
        if quality not in QUALITY_ORDER:
            quality = "unverified"
        per_market[market]["quality_counts"][quality] += 1
        refs = item.get("source_refs", [])
        if isinstance(refs, list):
            for ref in refs:
                if isinstance(ref, str) and ref.strip() and ref not in per_market[market]["source_refs"]:
                    per_market[market]["source_refs"].append(ref)
        accepted.append(item)

    coverage = []
    for market, stats in per_market.items():
        source_count = len(stats["source_refs"])
        coverage.append({
            "market_group": market,
            "message_count": stats["messages"],
            "distinct_source_ref_count": source_count,
            "source_refs": stats["source_refs"],
            "quality_counts": stats["quality_counts"],
            "status": "sufficient_for_review" if source_count >= min_sources_per_market else "insufficient_provenance",
        })

    insufficient = [item["market_group"] for item in coverage if item["status"] != "sufficient_for_review"]
    brief = build_collaboration_brief(accepted)
    return {
        "round_version": "1.0.0",
        "mode": "evidence_gated_deterministic_round",
        "status": "ready_for_human_review" if not insufficient else "incomplete_evidence",
        "requested_market_groups": requested,
        "represented_market_groups": [item["market_group"] for item in coverage if item["message_count"]],
        "insufficient_provenance_markets": insufficient,
        "source_coverage": coverage,
        "collaboration_brief": brief,
        "review_gate": {
            "minimum_distinct_source_refs_per_market": min_sources_per_market,
            "passed": not insufficient,
            "meaning": "Provenance coverage only; sources are not independently authenticated and values are not validated.",
        },
        "limitations": [
            "This assembles existing caller-supplied messages; it does not schedule or invoke autonomous AI agents.",
            "A source reference is a provenance pointer, not proof that a source is trustworthy.",
            "Quality labels are metadata and are not independently authenticated.",
            "Cross-market comparisons require analyst review of instruments, units, time windows and methods.",
            "No live data retrieval, investment recommendation, or order execution occurs.",
        ],
        "research_only": True,
    }
