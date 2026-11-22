# Research Execution Sandbox Architecture

Status: deterministic offline simulation and pure research calculations only. No brokerage connectivity, wallet access, private-key storage, transaction signing, order submission, or live trading is implemented.

## Components

- **Wallet security boundary:** no private keys, seed phrases, wallet exports, or signing credentials are accepted. Secret-like input should be rejected and redacted from logs and errors.
- **Transaction review fixtures:** synthetic transaction-shaped objects only; no signing or broadcast adapter.
- **Execution simulator:** `backend/app/research_execution_simulator.py` implements an in-memory state machine: NEW, ACKNOWLEDGED, PARTIALLY_FILLED, FILLED, CANCELLED, REJECTED and EXPIRED. Decimal arithmetic is used for quantities, prices and fees; timestamps must be timezone-aware; idempotency keys avoid duplicate fixture orders.
- **Market-making research:** `backend/app/market_making_research.py` computes mid, spread, and indicative quote sensitivity from caller-supplied snapshots. It rejects stale, future, crossed, non-positive and non-finite books. No venue polling or order API payloads are generated.
- **Historical data:** see `HISTORICAL-TRADE-LOG-INGESTION.md`. The approximately 37 MB archive has not been supplied; no import is claimed.

## Guardrails

No exchange or broker clients, order routing, order placement/cancellation, private-key handling, transaction signing, or broadcasting. Simulated fills are synthetic arithmetic, not venue fills or estimates of actual execution quality. Market-making outputs are indicative research values, not executable quotes.
