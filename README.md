# MARKET-MIND-AI

**Open-source, Bloomberg Terminal-inspired global market intelligence and research platform.**

MARKET-MIND-AI is designed as a modular, multi-asset workspace for market data, quantitative research, macroeconomic context, financial-document intelligence, advanced charting, and explainable analytics. It aims to bring professional research workflows into one configurable interface using open-source components and authorized data sources.

> **Scope:** This project is a market-information and research platform. It does not place orders, connect to brokerage execution endpoints, or provide personalized buy/sell instructions. The paper-trading module has been removed from the product scope.

## Product vision

Build a professional financial information terminal with:
- A customizable multi-panel workspace and command/search bar.
- Cross-asset monitoring for equities, ETFs, indices, FX, commodities, rates, bonds, and digital-asset market data where legally available.
- Streaming and historical data adapters with source, timestamp, delay, and quality metadata.
- Advanced interactive charts, watchlists, heatmaps, screeners, alerts, and comparison tools.
- Quantitative research: indicators, factor analytics, correlations, volatility, drawdowns, breadth, seasonality, and statistical testing.
- Company and instrument profiles, financial statements, filings, earnings transcripts, and event calendars.
- Macro dashboards for rates, inflation, employment, central-bank decisions, and economic releases.
- News and document search with citations and source traceability.
- A central AI research orchestrator with specialist analytical workers, shared verified knowledge, and worker-specific research memory.
- Reproducible research notebooks, backtesting for historical evaluation, and complete experiment/audit records.

## Core design principles

1. **Evidence before narrative:** every analytical statement should identify its source, timestamp, methodology, and limitations.
2. **One intelligence core:** specialist workers are lightweight analytical modules, not separate AI models. A configurable local model adapter may assist with summarization and explanation.
3. **Deterministic calculations:** numerical indicators and statistics are computed by tested code, not invented by an LLM.
4. **No unsupported precision:** stale, missing, delayed, or low-quality data must be visibly labelled.
5. **No execution layer:** no broker credentials, order placement, automated trading, or paper-trading simulator.
6. **Validated learning:** changes to analytical methods require tests, historical evaluation, versioning, review, and rollback.
7. **Open-source compliance:** integrations must respect upstream licences, attribution, terms of service, and redistribution restrictions.

## Terminal modules

| Module | Purpose |
|---|---|
| Market Overview | Global indices, asset classes, sessions, breadth, and market status |
| Instrument Workbench | Instrument profile, quote history, fundamentals, events, and related instruments |
| Advanced Charting | Candlesticks, multi-pane layouts, indicators, annotations, and custom intervals |
| Market Screener | User-defined filters across supported instruments and datasets |
| Quant Research | Returns, volatility, correlations, factor studies, drawdowns, and statistical tests |
| Macro & Rates | Economic series, yield curves, central-bank events, and macro comparisons |
| News & Filings | Search, classification, document extraction, and citation-grounded summaries |
| Flow & Liquidity Analytics | Volume, turnover, spread and order-book statistics when supported by the data source |
| Alerts | Configurable informational alerts for price, volume, volatility, events, and data quality |
| Research Studio | Saved queries, notebooks, reports, reproducible experiments, and audit history |
| Workflow Canvas | Node-based visual research pipelines inspired by composable workflow editors |
| AI Research Desk | Central orchestration of specialist analytical workers and source-grounded explanations |

## Analytical worker framework

The target architecture supports **550+ lightweight analytical workers** grouped into specialist departments. The count is an extensible design target, not a claim that 550 independent AI models are required.

Example departments:
- Technical indicators and price action
- Market structure and trend analysis
- Volatility and statistical analysis
- Volume, liquidity, and market microstructure
- Cross-asset relationships and correlations
- Equity fundamentals and company events
- Macro-economics, rates, and currencies
- Commodities and futures research
- News, filings, and document intelligence
- Data quality, anomaly detection, and validation
- Risk measurement and portfolio analytics
- Research methodology and experiment validation

Each worker should expose a typed input/output contract, methodology, required datasets, confidence/evidence fields, tests, version, and change history. Worker memory stores prior research outcomes and validated lessons; it must not silently rewrite production methodology.

## Timeframe and chart coverage

The chart engine should support common intervals including 1m, 3m, 5m, 15m, 30m, 45m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, and 1M, plus provider-supported custom aggregation. Availability depends on the instrument, exchange, provider, and historical retention.

## Suggested technology foundation

- **Frontend:** React, TypeScript, a professional component system, and React Flow for the workflow canvas.
- **Charts:** a maintained financial charting library with documented licence and data-volume limits.
- **Backend:** Python, FastAPI, Pydantic, and asynchronous data services.
- **Research:** NumPy, pandas/Polars, SciPy, statsmodels, scikit-learn, and carefully selected quantitative libraries.
- **Storage:** PostgreSQL for core records; TimescaleDB or another time-series store when justified; object storage for documents; optional vector search for retrieval.
- **Streaming:** WebSocket ingestion and a message broker when throughput requires it.
- **AI:** one central orchestrator with a pluggable local-model adapter; AI output must remain grounded in retrieved evidence.
- **Operations:** Docker, structured logs, metrics, tracing, automated tests, dependency scanning, and reproducible builds.

Technology choices are proposals until dependencies, licences, maintenance status, and deployment requirements have been reviewed.

## Repository layout

```text
MARKET-MIND-AI/
├── apps/
│   ├── terminal-web/          # Multi-panel terminal interface
│   └── api/                    # FastAPI application
├── core/
│   ├── orchestration/          # Central research intelligence
│   ├── contracts/              # Shared typed schemas
│   ├── governance/             # Permissions, audit, versioning
│   └── memory/                 # Verified shared and worker memory
├── market_data/
│   ├── adapters/               # Provider-specific connectors
│   ├── streaming/              # WebSocket and event ingestion
│   ├── normalization/          # Canonical market-data models
│   └── quality/                # Freshness, gaps, and validation
├── analytics/
│   ├── indicators/
│   ├── fundamentals/
│   ├── macro/
│   ├── microstructure/
│   ├── statistics/
│   └── portfolio_metrics/
├── workers/                    # Specialist analytical modules
├── workflows/                  # Visual workflow definitions
├── research/
│   ├── backtesting/            # Historical method evaluation only
│   ├── experiments/
│   └── reports/
├── knowledge/
│   ├── dictionary/
│   └── methodologies/
├── tests/
├── docs/
├── infra/
└── README.md
```

## Data-source policy

The platform must use official, licensed, or otherwise authorized sources. Provider adapters should declare:
- Supported asset classes, exchanges, fields, and intervals.
- Whether data is real-time, delayed, end-of-day, or historical.
- Rate limits, retention, attribution, and redistribution restrictions.
- Timezone, currency, corporate-action, and symbol-mapping conventions.
- Data-quality checks and fallback behavior.

A free endpoint is not automatically approved for commercial use or redistribution. Bloomberg data, terminals, proprietary identifiers, and proprietary content must not be copied or redistributed without the required rights.

## Security and governance

- Keep API keys and credentials outside source control.
- Use least-privilege access and encrypted secrets.
- Validate all external data and uploaded documents.
- Record source provenance and analytical method versions.
- Pin dependencies and review licences before adoption.
- Run unit, integration, data-contract, and regression tests.
- Require review before changing production analytics or worker definitions.

## Development status

This repository is the project foundation. Features should be marked **planned**, **in progress**, or **implemented and tested** only when supported by working code and tests. The roadmap is in [docs/ROADMAP.md](docs/ROADMAP.md), and the architecture is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Disclaimer

MARKET-MIND-AI is intended for software development, education, financial data exploration, and research. It is not a broker, exchange, investment adviser, or execution platform. Market data may be delayed, incomplete, or incorrect. Users are responsible for complying with data-provider terms and applicable laws.
