# TradingAgents-Inspired Market Research Adapter

## Status
This is a **research-only adaptation plan**, not a vendored copy or a runtime dependency on TauricResearch/TradingAgents.

## Upstream
- Repository: https://github.com/TauricResearch/TradingAgents
- Upstream README: https://github.com/TauricResearch/TradingAgents/blob/main/README.md
- License: Apache-2.0 (upstream LICENSE): https://github.com/TauricResearch/TradingAgents/blob/main/LICENSE
- Upstream framework uses LangGraph and multiple LLM providers. Its full runtime has a distinct dependency tree and should not be merged blindly into MARKET-MIND-AI's FastAPI/React stack.

## What is adapted
The analyst/research workflow concepts are mapped to MARKET-MIND-AI's existing research orchestrator and council:
- company fundamentals
- market data quality and descriptive analysis
- news and source verification
- macroeconomic research
- opposing-evidence review
- evidence audit and synthesis

Implementation instructions are in [the TradingAgents market research skill](../.agents/skills/tradingagents-market-research/SKILL.md).

## Data-source mapping
| Upstream-style research area | MARKET-MIND-AI adapter direction | Requirements |
|---|---|---|
| Price/volume analysis | Existing OHLCV input and validation | Timestamp, timezone, exchange, provider, gaps and duplicates |
| Fundamentals | SEC EDGAR filings and vendor financial statements | Filing date vs period end, source provenance |
| News/sentiment | Existing RSS/news and optional Agent Reach connector | Link, publisher, date, fact vs opinion |
| Macro | Optional FRED or official central-bank releases | Series ID, units, frequency, release/vintage |
| Bull/bear debate | Existing council roles | Evidence-based counterarguments, no fabricated consensus |
| Final report | Existing research orchestrator | Source ledger, caveats, uncertainties |

## Compatibility and resource notes
- The upstream project requires a newer Python runtime and brings a LangGraph/LLM-provider dependency stack; do not install its dependencies into the current backend without a separate compatibility review.
- Existing MARKET-MIND-AI architecture uses a bounded research council and a shared inference provider in some paths. Distinct role prompts are not separate models.
- Keep this adapter optional and avoid adding paid API requirements. Public/free sources may rate-limit or have coverage restrictions.
- Do not commit credentials. Keep secrets in local environment configuration.

## Explicit scope boundary
This adaptation is for neutral market research and educational data analysis. It does not include trading decision agents, portfolio-manager approval, broker/exchange execution, order routing, or real-money automation.

## Attribution
This document is an original integration guide inspired by the public architecture of TauricResearch/TradingAgents. It is not a copy of upstream source code. Consult the upstream Apache-2.0 license before copying or redistributing any source files.
