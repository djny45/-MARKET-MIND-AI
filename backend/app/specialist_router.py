"""Transparent, deterministic specialist routing for research briefs.

Routing selects worker profiles from task language and registered capabilities.
It does not invoke models, fetch market data, or make investment decisions.
"""
import re
from .workers import list_workers

_STOP = {
    "the", "and", "for", "with", "from", "that", "this", "are", "was", "were",
    "have", "has", "into", "about", "please", "analyze", "analysis", "research",
    "market", "data", "task", "review", "using", "provide", "help", "what",
}
_DEPARTMENT_TERMS = {
    "technical_analysis": {"technical", "indicator", "rsi", "macd", "trend", "momentum", "breakout", "candlestick"},
    "market_structure": {"structure", "support", "resistance", "market", "price_action"},
    "volume_liquidity": {"volume", "liquidity", "orderbook", "order_book", "spread", "depth"},
    "volatility": {"volatility", "variance", "std", "standard_deviation", "risk", "drawdown"},
    "quantitative_research": {"backtest", "backtesting", "forecast", "predictive", "statistics", "regression", "model"},
    "cross_asset": {"cross_asset", "correlation", "spillover", "intermarket", "multi_asset"},
    "equities_fundamentals": {"equity", "stock", "earnings", "fundamental", "revenue", "valuation"},
    "macroeconomics": {"macro", "inflation", "gdp", "economy", "economic", "policy", "central_bank"},
    "foreign_exchange": {"forex", "fx", "currency", "exchange_rate"},
    "commodities": {"commodity", "commodities", "gold", "oil", "energy"},
    "fixed_income": {"bond", "bonds", "yield", "yield_curve", "fixed_income"},
    "crypto_markets": {"crypto", "bitcoin", "ethereum", "token", "blockchain"},
    "news_intelligence": {"news", "headline", "sentiment", "media"},
    "event_analysis": {"event", "earnings_call", "announcement", "event_impact"},
    "portfolio_analytics": {"portfolio", "allocation", "exposure", "diversification"},
    "data_quality": {"quality", "missing", "stale", "integrity", "validation", "cleaning"},
    "risk_analytics": {"risk", "var", "value_at_risk", "stress", "loss"},
    "pattern_recognition": {"pattern", "anomaly", "recognition", "shape"},
    "research_validation": {"validate", "validation", "test", "benchmark", "evidence", "robustness"},
    "market_regimes": {"regime", "regimes", "bull", "bear", "sideways", "state"},
}

def route_research_brief(brief, data=None, limit=5):
    """Return ranked specialist profiles and auditable keyword-match rationale."""
    if not isinstance(brief, str) or not brief.strip() or len(brief) > 4000:
        raise ValueError("brief must be a non-empty string of at most 4000 characters")
    if data is not None and not isinstance(data, (dict, list)):
        raise ValueError("data must be an object or array")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 20:
        raise ValueError("limit must be between 1 and 20")
    text = brief.lower()
    if data is not None:
        import json
        text += " " + json.dumps(data, ensure_ascii=False, sort_keys=True).lower()[:6000]
    tokens = set(re.findall(r"[a-zA-Z0-9_]{2,}", text)) - _STOP
    scored = []
    for worker in list_workers():
        terms = _DEPARTMENT_TERMS.get(worker["department"], set())
        matches = sorted(tokens & terms)
        # Specialty terms provide a small secondary signal, not fabricated expertise.
        specialty = worker["specialty"].lower().replace("_", " ")
        specialty_tokens = set(re.findall(r"[a-zA-Z0-9_]{2,}", specialty))
        specialty_matches = sorted(tokens & specialty_tokens)
        score = len(matches) + 0.5 * len(specialty_matches)
        if score:
            scored.append({
                "worker_id": worker["id"], "name": worker["name"],
                "department": worker["department"], "specialty": worker["specialty"],
                "matched_department_terms": matches,
                "matched_specialty_terms": specialty_matches,
                "routing_score": round(score, 2),
            })
    scored.sort(key=lambda item: (-item["routing_score"], item["worker_id"]))
    selected = scored[:limit]
    return {
        "routing_mode": "deterministic_keyword_capability_match",
        "brief": brief.strip(),
        "candidate_count": len(scored),
        "selected_count": len(selected),
        "candidates": selected,
        "limitations": [
            "This is transparent keyword routing, not semantic understanding or an LLM decision.",
            "Worker profiles are templates sharing one inference provider, not independent model instances.",
            "A low or empty match is not evidence that the task is impossible; manual assignment may be better.",
            "No market data is fetched and no trading or investment instruction is produced.",
        ],
    }
