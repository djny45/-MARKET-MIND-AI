# Licensed data inventory and compliance-review preparation

Status: **inventory complete; legal/licensing review BLOCKED**. This document
records what actually exists. It does not authorize any live or delayed data
source and contains no credentials.

## 1. Current inventory (verified 2026-11-25)

| Source / adapter | Present | Classification | Provenance | License / legal status | Runtime use |
| --- | --- | --- | --- | --- | --- |
| `synthetic-fixture` | Yes | Synthetic | Generated locally by the research adapter | No third-party license; explicitly labelled synthetic | Available for development/integration only |
| Yahoo historical helpers | Code only | Historical research helper, not real-time | Best-effort public endpoint; not execution-grade | Redistribution/API terms **not verified**; source is in the gate's unauthorized list | Blocked from live/delayed claims |
| Stooq historical helpers | Code only | Historical research helper | Best-effort public endpoint | Terms **not verified**; source is in the gate's unauthorized list | Blocked from live/delayed claims |
| `alpha-advantage` | Gate entry only | Candidate licensed source | Not configured | `pending_license_review`; credentials required | Blocked until written review |
| `market-data-api-center` | Gate entry only | Candidate licensed source | Not configured | Authorized by gate structure only; credentials required; no product/contract on file | Blocked in practice |
| `binance-public` | **Yes — live** | Public exchange REST (unlicensed public endpoints) | Operator-attested via `MARKET_MIND_ATTESTED_DATA_SOURCES`; bars stored with `source=binance-public`, `status=live` | Exchange public-API terms only. **Not** a licensed real-time feed: no redistribution right, no SLA, no execution-grade guarantee. Legal review still required for redistribution | BTCUSD/ETHUSD/SOLUSD/BNBUSD 15m bars, research + paper simulation only |
| `MARKET_MIND_ATTESTED_DATA_SOURCES` | `binance-public` | Attestation allowlist | Operator environment | Operator attested the public source above | `/api/market-data/store` accepts live claims only for attested sources |

Live evidence (verified 2026-11-25):

```
GET /api/providers/status   (authenticated)
-> "status": "live_provider_configured"
-> "live_providers": ["binance-public"]
-> "market_data_note": "... public exchange endpoints, not a licensed
   real-time feed; no redistribution or execution-grade guarantee is implied."

market_bars: BNBUSD/BTCUSD/ETHUSD/SOLUSD, interval=15m,
             source=binance-public, status=live, ~148 bars each,
             latest retrieval age <= 31s
```

The endpoint derives this from the stored bars and the attestation allowlist
rather than asserting a fixed value, so it cannot drift from reality again.

Gate manifest (`DataLicensingGate`):

| Review flag | Authorized | Pending | Unauthorized |
| --- | --- | --- | --- |
| `license_review_completed=false` | `market-data-api-center` | `alpha-advantage` | scrapers, Stooq, Yahoo chart, unknown custom |
| `license_review_completed=true` (hypothetical) | `alpha-advantage`, `market-data-api-center` | none | unchanged |

This repository does **not** set the review flag to true.

## 2. Provenance record required for each licensed source

An operator must supply, and archive outside the repository:

1. Provider legal name, exact product/SKU and plan tier.
2. License/terms document with effective date, including caching, redistribution,
   delay, attribution, retention and termination clauses.
3. Source ID to be placed in `MARKET_MIND_ATTESTED_DATA_SOURCES`.
4. Retrieval method and endpoint; confirmation that TLS is used.
5. Data classification: live / delayed / historical / synthetic.
6. Credential location: 0600 EnvironmentFile, never source code or logs.
7. Named approver, legal reviewer, review date and written decision.
8. Evidence: archived license PDF, approval email/ticket, and a redacted
   `/api/providers/status` response after configuration.
9. Retention/deletion rule for cached bars and backups containing licensed data.

No item above is currently satisfied for a live or delayed source.

## 3. Compliance-review package preparation

Ready for a legal/licensing reviewer:

- `docs/MARKET_DATA_LICENSING.md` — implementation facts and unresolved steps.
- `docs/DATA-LICENSING-GATE.md` — gate rules and usage.
- `backend/app/data_licensing_gate.py` — allowlist/pending/blocked logic.
- `backend/app/market_data.py` — live/delayed/historical/synthetic labelling.
- `backend/tests/test_data_licensing_gate.py` — 5 tests covering fail-closed rules.
- `GET /api/providers/status` evidence command (above).

Reviewer decision required: approve or reject each product, then supply the
attested source ID and written approval. Until then, public gate G5 remains
**BLOCKED** and no live/delayed label may be enabled.

No prices, credentials or approvals were invented.
