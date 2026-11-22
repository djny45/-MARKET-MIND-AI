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
# stageshow is a UI-only playbook; do not attach it to analytical workers.
SKILL_BY_DEPARTMENT = {
    "technical_analysis": ["trader-scanner", "autohedge-quant-analysis", "autohedge-director-coordination", "autohedge-market-making-lab"],
    "market_structure": ["trader-scanner", "autohedge-quant-analysis", "autohedge-director-coordination", "autohedge-market-making-lab"],
    "volume_liquidity": ["trader-scanner", "autohedge-quant-analysis", "autohedge-director-coordination", "autohedge-market-making-lab"],
    "volatility": ["trader-risk", "trader-timemachine", "autohedge-quant-analysis", "autohedge-risk-assessment"],
    "quantitative_research": ["trader-timemachine", "autohedge-quant-analysis", "autohedge-thesis-validation", "autohedge-market-making-lab"],
    "cross_asset": ["trader-analyst", "trader-news", "autohedge-sentiment-analysis", "autohedge-director-coordination"],
    "equities_fundamentals": ["trader-analyst", "autohedge-sentiment-analysis"],
    "macroeconomics": ["trader-news", "trader-analyst", "autohedge-sentiment-analysis"],
    "foreign_exchange": ["trader-news", "autohedge-sentiment-analysis"],
    "commodities": ["trader-news", "autohedge-sentiment-analysis"],
    "fixed_income": ["trader-news", "trader-analyst", "autohedge-sentiment-analysis"],
    "crypto_markets": ["trader-news", "trader-scanner", "autohedge-quant-analysis", "autohedge-sentiment-analysis", "autohedge-public-token-data"],
    "news_intelligence": ["trader-news", "autohedge-sentiment-analysis", "autohedge-director-coordination"],
    "event_analysis": ["trader-news", "trader-analyst", "autohedge-sentiment-analysis"],
    "portfolio_analytics": ["trader-risk", "trader-budget", "autohedge-risk-assessment"],
    "data_quality": ["trader-risk", "rea-ci-tests-audit", "autohedge-risk-assessment", "autohedge-thesis-validation"],
    "risk_analytics": ["trader-risk", "trader-budget", "autohedge-risk-assessment", "autohedge-market-making-lab"],
    "pattern_recognition": ["trader-scanner", "trader-timemachine", "autohedge-quant-analysis"],
    "research_validation": ["trader-timemachine", "trader-risk", "rea-ci-tests-audit", "rea-analysis-optimization", "reverse-engineer-anything", "rea-tool-design", "autohedge-thesis-validation", "autohedge-director-coordination"],
    "market_regimes": ["trader-timemachine", "trader-news", "autohedge-quant-analysis", "autohedge-sentiment-analysis"],
}


def list_workers():
    workers = []
    for i in range(550):
        department = DEPARTMENTS[i % len(DEPARTMENTS)]
        specialty = SPECIALTIES[(i // len(DEPARTMENTS)) % len(SPECIALTIES)]
        pack_skill_refs = [
            f"mm-skill-{((i * 2) % 300) + 1:03d}",
            f"mm-skill-{((i * 2 + 1) % 300) + 1:03d}",
        ]
        workers.append({
            "id": f"worker_{i+1:03d}",
            "name": f"{specialty.replace('_', ' ').title()} Analyst {i+1:03d}",
            "department": department,
            "specialty": specialty,
            "kind": "ai_analytical_worker",
            "model": "shared_central_intelligence",
            "memory_namespace": f"workers/worker_{i+1:03d}",
            "skill_refs": list(dict.fromkeys(["autohedge-director-coordination"] + SKILL_BY_DEPARTMENT.get(department, []) + pack_skill_refs)),
            "status": "template",
            "note": "AI analytical worker template; execution requires an implemented, validated handler in the shared central intelligence runtime."
        })
    return workers
