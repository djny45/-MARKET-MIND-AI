# Four-Market Terminal — End-to-End Validation Report

Generated 2026-11-26. Branch `feat/four-market-terminal`, HEAD `3ca5e9369ec475f3923c1a4892cd2da970d62670` (no commit made in this phase; all work remains uncommitted as found). This report records **actual** results. It does not claim LIVE status for any source.

## 1. Provider adapters identified (from `docs/FOUR-MARKET-PLATFORM.md`)

| Market | Adapter | Endpoint used | Native observation |
| --- | --- | --- | --- |
| US | `yahoo-us-equities` | Yahoo Finance chart v8 | Daily close, NYSE/NASDAQ/ETF/index |
| India | `yahoo-india-nse-bse` | Yahoo Finance chart v8, `.NS`/`.BO` suffixes | Daily close, NSE/BSE |
| Forex | `ecb-reference-rates` | ECB Data API EXR CSV | Daily EUR reference fixing |
| Crypto | `coingecko-public` | CoinGecko simple price | Aggregated public spot snapshot |

All four are implemented in `backend/app/provider_adapters.py`, wired into `backend/app/four_market_terminal.py`, exposed through `/api/terminal/*` in `backend/app/main.py`, and rendered by `frontend/src/FourMarketTerminal.tsx`.

## 2. Provider-by-provider validation evidence

Evidence: `docs/external-evidence/four-market-provider-validation.json`.

Constraints applied: **1 request per symbol**, 8 symbols total, 8s timeout, 4 MB cap, no credentials, no cookies, no writes, **empty attestation set** (so a LIVE/DELAYED claim was structurally impossible).

| Market | Symbol | Result | Last | Event time (UTC) | Exchange-local | Elapsed |
| --- | --- | --- | --- | --- | --- | --- |
| US | AAPL | observed / HISTORICAL | 355.58 USD | 2026-11-25T14:30:00Z | 2026-11-25T09:30:00-05:00 | 0.198s |
| US | SPX | observed / HISTORICAL | 7,182.78 USD | 2026-11-25T14:30:00Z | 2026-11-25T09:30:00-05:00 | 0.101s |
| India | RELIANCE | observed / HISTORICAL | 1,396.20 INR | 2026-11-26T03:45:00Z | 2026-11-26T09:15:00+05:30 | 0.175s |
| India | TCS (BSE `.BO`) | observed / HISTORICAL | 2,640.00 INR | 2026-11-26T03:45:00Z | 2026-11-26T09:15:00+05:30 | 0.119s |
| Forex | EURUSD | observed / HISTORICAL | 1.0935 | 2026-11-25T00:00:00Z | n/a (reference fixing) | 3.055s |
| Forex | USDINR | observed / HISTORICAL | 92.2350 | 2026-11-25T00:00:00Z | n/a (reference fixing) | 3.178s |
| Crypto | BTCUSD | observed / HISTORICAL | 60,432.00 USD | 2026-11-26T10:49:37Z | n/a (24/7 market) | 0.298s |
| Crypto | ETHUSD | observed / HISTORICAL | 1,692.58 USD | 2026-11-26T10:49:37Z | n/a (24/7 market) | 0.307s |

Direct endpoint metadata probes: Yahoo chart HTTP 200, ECB CSV HTTP 200, CoinGecko simple price HTTP 200. No rate-limit headers were present on those three single requests.

**Timestamp verification (#10):** the Yahoo chart payload declares `exchangeTimezoneName: Asia/Kolkata` and `gmtoffset: 19800` for Indian symbols. That value is now carried into `MarketQuote.exchange_timezone`, validated against the IANA database, and rendered as a derived `timestamp_exchange_local` alongside the canonical UTC instant. US symbols resolve to `America/New_York`. The observed local times (09:30 EST, 09:15 IST) match the actual exchange session opens, confirming the mapping is correct. ECB publishes a date, not a timezone-bearing instant, so **no** timezone is invented for FX; crypto is 24/7 and has no exchange session. Unknown IANA names become `null` rather than a guessed offset.

**Normalized contract (#6):** all eight observations validated as `MarketQuote` objects across four asset classes. Each carried `source`, `timestamp`, `retrieved_at`, `status`, `status_label`, `quote_type`, and derived `age_seconds`/`stale`/`max_age_seconds`. No bid/ask was populated on any quote. The FX quote is `reference`; crypto is `mid`; equities/indices are `close`.

## 3. API and dashboard integration (#7, #8)

Evidence: `docs/external-evidence/` plus real browser screenshots below. Exercised with `TestClient` against a temporary SQLite DB (the live server on port 8000 has auth enabled; it was not bypassed or modified):

| Check | Result |
| --- | --- |
| Instrument search US (`q=AAPL`) | HTTP 200, 1 instrument |
| Instrument search India (`q=RELIANCE`) | HTTP 200, 1 instrument |
| Instrument search forex (`q=EURUSD`) | HTTP 200, 1 instrument |
| Instrument search crypto (`q=BTC`) | HTTP 200, 2 instruments |
| Instrument master | HTTP 200, 10 instruments |
| Watchlist route | HTTP 200, empty list |
| Chart history route | HTTP 200, 0 stored bars (no bars ingested yet) |
| Filtered board (`markets=us&symbols=us:AAPL`) | HTTP 200, 1 quote, real provider data |
| Full board | HTTP 200, 17 quotes |
| Summary / providers / provider-status | HTTP 200, all four adapters listed |

Real data through the public API for all four markets: AAPL 355.58 (historical, America/New_York), RELIANCE 1,396.20 (historical, Asia/Kolkata), EURUSD 1.0935 (historical), BTCUSD 60,444.00 (historical). All were labelled `HISTORICAL` despite crypto being ~41s old, because no source is attested.

## 4. Failure, staleness and recovery (#9)

Evidence: `docs/external-evidence/four-market-resilience.json` from `backend/tests/test_four_market_resilience.py`.

| Scenario | Result |
| --- | --- |
| All four providers fail | 17/17 UNAVAILABLE, no prices, every row has a reason |
| US recovers, others remain down | US 5/5 usable and FRESH; India/forex/crypto still UNAVAILABLE; no stale price leaked |
| Attested LIVE quote aged 600s | correctly `stale=true`, market HEADLINE `ALL OBSERVATIONS STALE` |
| Attested LIVE quote aged 10s | `stale=false`, market FRESH |
| No attestation | observation labelled HISTORICAL, never LIVE |
| CoinGecko HTTP 429 observed live | converted to UNAVAILABLE with `Retry-After: 60s` in the reason |

## 5. Status-label clarity (#11)

Real browser evidence (`docs/external-evidence/screenshots/four-market-evidence.json`): 4 panels, 17 quote rows, **all 17 badges HISTORICAL**, and the legend renders all five labels `LIVE`, `DELAYED`, `HISTORICAL`, `SYNTHETIC`, `UNAVAILABLE`. The header strip prominently states `NO ATTESTED SOURCE — LIVE/DELAYED UNAVAILABLE`. Zero console errors. One `/api/terminal/four-market` call.

## 6. Screenshots (#11)

Real headless-Chromium captures against an isolated research-mode backend and the built frontend:

- `docs/external-evidence/screenshots/four-market-terminal-full.png`
- `docs/external-evidence/screenshots/four-market-terminal-header.png`
- `docs/external-evidence/screenshots/four-market-us-panel.png`
- `docs/external-evidence/screenshots/four-market-india-panel.png`
- `docs/external-evidence/screenshots/four-market-terminal-narrow.png`

The India panel visibly shows the exchange-local `2026-11-26T09:15:00+05:30` alongside the UTC instant and retrieval time.

## 7. Licensing / redistribution (#12)

No feed was enabled as LIVE. No attestation entry was set in any persistent config. `docs/FOUR-MARKET-PLATFORM.md` records that public accessibility is not redistribution permission, includes the NSE data-policy links, and states that promotion to LIVE/DELAYED requires a recorded entitlement, permitted-use and redistribution review. CoinGecko's response body explicitly points to paid plans for higher rate limits; this was recorded as a blocker, not worked around by spoofing or credential use.

## 8. Changes made in this phase

- `backend/app/market_quotes.py` — `exchange_timezone` field with IANA validation, derived `timestamp_exchange_local` in payloads.
- `backend/app/provider_adapters.py` — parse/validate Yahoo `exchangeTimezoneName`; explicit no-timezone for FX/crypto; surface `Retry-After` on HTTP errors; per-provider serialized, cross-provider parallel fetching (full board 19.7s → ~4–6s).
- `backend/tests/test_provider_adapters.py` — 5 timezone tests + 1 rate-limit test.
- `backend/tests/test_four_market_resilience.py` — new offline failure/recovery evidence test.
- `frontend/src/FourMarketTerminal.tsx` + UI tests — render exchange-local timestamp with timezone tooltip.
- `scripts/validate_four_market_providers.py`, `scripts/validate_four_market_api.py`, `scripts/validate_four_market_flow.py` — bounded evidence collectors.
- `docs/FOUR-MARKET-PLATFORM.md` — adapter and terminal documentation.
- Evidence files under `docs/external-evidence/`.

All Phase 3 changes were preserved. Nothing was deleted, reset, reverted, merged or deployed. No credentials were exposed; no real-money trading was enabled.

## 9. Test results (#14)

| Suite | Result |
| --- | --- |
| Backend `unittest discover` | **1401 tests OK, 1 skipped** |
| Frontend `vitest run` | 22 files, 143 tests passed |
| Frontend `npm test` | 10 passed |
| `npm run typecheck:test` | clean |
| `npm run build` | production bundle created |

## 10. Remaining blockers

1. **CoinGecko public rate limit** — ~2 req/min/IP, `Retry-After: 60`. A three-symbol crypto refresh cannot be served reliably from the free public endpoint. Mitigated (degrades to UNAVAILABLE, never fabricates), not solved. Requires a licensed plan or fewer crypto symbols.
2. **No licensed feed / no attestation** — no source is operator-attested, so every observation is HISTORICAL. This is intentional and is not a defect, but it means no LIVE data is available.
3. **Chart history is empty** — the normalized quote adapters do not write OHLCV bars into the SQLite bar store; chart pages show no stored bars. Historical ingestion is a separate implementation-sequence item in the platform doc.
4. **Live server on port 8000 has auth enabled** — browser validation used an isolated research-mode server with a temporary DB; no shared server or credentials were touched.
5. **No commit made** — per instruction, all work remains uncommitted on `feat/four-market-terminal`.

## 11. Evidence-based completion

| Phase item | Status |
| --- | --- |
| 1 Identify four adapters | 100% |
| 2 Verify four implementations | 100% |
| 3 Bounded public endpoint exercise | 100% |
| 4 Record responses/timestamps/errors/rate limits | 100% |
| 5 Never label unattested data LIVE | 100% |
| 6 Normalized quote contract across asset classes | 100% |
| 7 Connect adapters to API + frontend | 100% |
| 8 Instrument search / watchlists / charts / filters | 90% (charts return no bars — no ingestion) |
| 9 Unavailable / stale / failure / recovery | 100% |
| 10 Exchange timezones | 100% |
| 11 UI status distinction + screenshots | 100% |
| 12 Licensing / redistribution before LIVE | 100% verification; no feed promoted (correct outcome) |
| 13 Preserve Phase 3 and safety controls | 100% |
| 14 Run all test suites + build | 100% |

**Overall evidence-based completion: 98.6%** (13 full items + one 90% item across 14 items). The single deduction reflects the absence of historical bar ingestion, which prevents chart pages from displaying stored data.

## 12. Exact revision

- Branch: `feat/four-market-terminal`
- HEAD (unchanged): `3ca5e9369ec475f3923c1a4892cd2da970d62670`
- No new commit was created in this phase.
