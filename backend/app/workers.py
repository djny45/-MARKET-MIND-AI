DEPARTMENTS = [
    "technical_analysis", "market_structure", "volume_liquidity", "volatility",
    "quantitative_research", "cross_asset", "equities_fundamentals", "macroeconomics",
    "foreign_exchange", "commodities", "fixed_income", "crypto_markets",
    "news_intelligence", "event_analysis", "portfolio_analytics", "data_quality",
    "risk_analytics", "pattern_recognition", "research_validation", "market_regimes",
]
SPECIALTIES = [
    "trend", "momentum", "mean_reversion", "breakout", "pullback",
    "volume_profile", "order_book", "volatility", "correlation", "seasonality",
    "relative_strength", "macro_context", "fundamentals", "event_impact",
    "data_integrity", "statistical_validation", "market_breadth", "regime_detection",
    "support_resistance", "candlestick_patterns", "liquidity_conditions",
    "yield_curve", "cross_market_spillover", "risk_metrics", "anomaly_detection",
    "research_synthesis", "earnings_quality", "economic_surprise",
]

# Skill references are guidance links only. They do not activate executable agents.
SKILL_BY_DEPARTMENT = {
    "technical_analysis": ["trader-scanner"],
    "market_structure": ["trader-scanner"],
    "volume_liquidity": ["trader-scanner"],
    "volatility": ["trader-risk", "trader-timemachine"],
    "quantitative_research": ["trader-timemachine"],
    "cross_asset": ["trader-analyst", "trader-news"],
    "equities_fundamentals": ["trader-analyst"],
    "macroeconomics": ["trader-news", "trader-analyst"],
    "foreign_exchange": ["trader-news"],
    "commodities": ["trader-news"],
    "fixed_income": ["trader-news", "trader-analyst"],
    "crypto_markets": ["trader-news", "trader-scanner"],
    "news_intelligence": ["trader-news"],
    "event_analysis": ["trader-news", "trader-analyst"],
    "portfolio_analytics": ["trader-risk", "trader-budget"],
    "data_quality": ["trader-risk"],
    "risk_analytics": ["trader-risk", "trader-budget"],
    "pattern_recognition": ["trader-scanner", "trader-timemachine"],
    "research_validation": ["trader-timemachine", "trader-risk"],
    "market_regimes": ["trader-timemachine", "trader-news"],
}


def list_workers():
    workers = []
    for i in range(550):
        department = DEPARTMENTS[i % len(DEPARTMENTS)]
        specialty = SPECIALTIES[(i // len(DEPARTMENTS)) % len(SPECIALTIES)]
        workers.append({
            "id": f"worker_{i+1:03d}",
            "name": f"{specialty.replace('_', ' ').title()} Analyst {i+1:03d}",
            "department": department,
            "specialty": specialty,
            "kind": "analytical_module",
            "model": "shared_central_intelligence",
            "memory_namespace": f"workers/worker_{i+1:03d}",
            "skill_refs": SKILL_BY_DEPARTMENT.get(department, []),
            "status": "template",
            "note": "Generated worker profile; activate only after implementation and validation."
        })
    return workers
