# Autonomous market discovery and research prioritization

MARKET-MIND-AI can choose **what to inspect next** from provider-supplied
instrument candidates. It should not require the operator to manually choose
India, US, crypto, or forex first. Coverage is still bounded by configured,
authorized providers and their licenses/rate limits.

## Current implementation

`backend/app/market_discovery.py` implements a provider-neutral queue builder.
Adapters provide candidate symbols, venue, timestamps, supported timeframes,
data availability, and normalized 0–1 measurements when available:

- data quality (required)
- activity
- volatility
- news attention
- social attention

The score is a transparent weighted **research-priority heuristic**, not a
prediction, asset recommendation, or trade signal. Missing optional evidence is
omitted and weights are renormalized; missing fields are disclosed and lower
confidence. Unavailable, stale, malformed-timestamp, or quality-unknown records
are excluded. Duplicate venue/symbol entries are removed.

The current module is a tested selection primitive. It does **not yet connect
itself to live provider adapters, social APIs, chart fetchers, or the central
orchestrator**. Those integrations must pass real provider evidence into this
contract before the full autonomous loop can be called operational.

## Intended next integration

1. Provider adapters enumerate only instruments they are authorized to expose.
2. The central intelligence core requests a candidate research queue and records
   the rationale for the selected batch.
3. Data adapters fetch OHLCV for supported timeframes and attach source,
   timestamp, delay, and quality metadata.
4. Existing deterministic chart research analyzes those datasets.
5. News/social adapters attach source-linked context only when entity matching
   is sufficiently confident; ambiguous matches remain unlinked.
6. The orchestrator produces a report with evidence, stale-data warnings,
   uncertainty, and provider coverage gaps.

## Guardrails

- No universal social-media scanning claim: platforms require supported public
  APIs, RSS, permissions, and compliance with terms/rate limits.
- No autonomous code/model self-modification. Research outcomes may inform
  versioned proposals, which require offline evaluation and review.
- No brokerage credentials, order routing, paper/live execution, or buy/sell
  outputs. This is a research-prioritization component.
- Scores are not validated for predictive accuracy or profitability.
