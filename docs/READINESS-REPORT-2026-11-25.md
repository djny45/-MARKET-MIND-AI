# MARKET-MIND-AI — Final readiness report

**Date:** 2026-11-25
**Scope:** finish every locally achievable operational task, prove it, and
separate it from what genuinely needs an outside party.
**Mode:** research-only, paper trading, `broker_execution=false`. No real money,
no broker orders, no wallet keys, nothing deployed publicly.

Every number below was measured on the running stack. Nothing is estimated,
and no blocked item is reported as passed.

---

## 1. Verdict

**Locally ready for research-only, paper-simulated use.** Not cleared for
public deployment.

| Dimension | Result |
|---|---|
| Acceptance items verified locally | **37 / 37** (all that can be resolved here) |
| Acceptance items blocked externally | 3 (ACC-029 S3, ACC-030 host drill, ACC-031 sign-off) |
| Public-ingress gates (G1–G6) | **0 / 6** — every one needs an external party |
| Overall (46-check table) | **37 PASS / 9 BLOCKED / 0 FAIL** |
| Runtime health | 6/6 services healthy, supervision loop alive |
| Ledger correctness | reconciles to **0.0000000000** |
| Test suite | **1331 / 1331** backend, 137 frontend, build clean |

Every check that can be resolved inside this environment passes: 37 of 37. The
nine blocked entries are 3 acceptance items plus 6 gates, and all nine require
an external party. None is counted as passing.

---

## 2. What I verified

### 2.1 Tests

| Suite | Result |
|---|---|
| Backend (CI-identical invocation) | 1331 OK, 1 skipped |
| Frontend node unit | 10 / 10 |
| Frontend vitest | 127 / 127, 21 files |
| Frontend production build | clean (`tsc` + bundle) |

The skipped test is a pre-existing environment skip, not a suppressed failure.

### 2.2 Live stack

| Check | Measured |
|---|---|
| Services healthy | 6 / 6 (`backend`, `proxy`, `supervisor`, `backup_scheduler`, `jupyter_bridge`, `market_feed`) |
| `/api/health` latency | 50/50 ok; median **0.9 ms**, p95 **1.0 ms**, max 41 ms |
| Kill-and-recover, SIGKILL ×6 | all six back in **0.8–2.5 s** |
| Ledger after the drill | `cash_mismatches=0/550`, delta `0.0000000000` |
| Portfolios / positions / trades | 550 / 2239 / 9403 |
| Worst drawdown | 1.48% (was a fictitious 40.24%) |
| Fees recorded | 9403/9403 trades, none null |
| Rankings | 550 rows, ranks 1–550 contiguous, sorted, reconciled to the ledger |

### 2.3 Market data — real, not fabricated

| Check | Result |
|---|---|
| Exchange reachability | **5 / 5** HTTP 200 (Binance, Coinbase, Kraken, Binance.US, Bybit) |
| Stored live bars | 4 symbols × ~148 bars, `source=binance-public`, `status=live` |
| Freshness | fetch age ≤ **31 s** |
| Price sanity | BTC ≈ $59.7k, ETH ≈ $1.68k, SOL ≈ $69.6, BNB ≈ $549 |
| Position marks vs live | drift **0.000%** across all 2200 crypto positions |

Live prices are real public exchange data. They are **not** a licensed
real-time feed and carry no redistribution or execution-grade guarantee.

### 2.4 Browser, responsiveness, accessibility

Driven in a real browser (Camoufox/Firefox), against the served page:

- Title, 80 position rows, 40 order rows, 4 market rows, 6 KPIs, fresh snapshot.
- Mobile: at 390 px the layout collapses to one column, tables scroll
  internally, widest element ends at 380 px — **no clipping**.
- Accessibility fixes confirmed live: one `h1`, three distinct table
  `aria-label`s, `role=status` + `aria-live=polite` on the status line,
  `lang=en`.
- Both routes render: Jupyter `/files/` and the loopback proxy.

### 2.5 Security

| Control | Result |
|---|---|
| Unauthenticated protected endpoints | 401 (7 endpoints, direct and via proxy) |
| Public endpoints stay open | `/api/health`, `/api/ready` → 200 |
| Mutating POST without CSRF header | 403 |
| Mutating POST with invalid CSRF | 403 |
| Cross-origin POST with valid CSRF | 403 |
| POST with no Origin header | 403 |
| Wrong origin at login | rejected: `Request origin is not allowed.` |
| JupyterHub API token in served files | **0 occurrences** |
| Real secrets in the working tree | none (only env-var names) |

The token that was previously embedded in the launcher and launcher HTML has
been removed and has since rotated, so the leaked value is also dead.

### 2.6 Backup and recovery

| Check | Result |
|---|---|
| `market_mind.db` backup | verified, restore-proven |
| **`paper_trading.db` backup** | verified, restore-proven (550 / 2239 / 9403, FKs clean) |
| Retention | enforced, default keep 30 |
| Off-host upload | not configured (external — see §4) |

Before this pass, the scheduler backed up only `market_mind.db`. The 550
portfolios and every trade were **unprotected**, and nothing surfaced that gap.

---

## 3. Defects found and fixed

Each was proven against the retained ledger; none was fixed by editing a number
to look right.

| # | Defect | Impact | Fix |
|---|---|---|---|
| 1 | SELL never credited proceeds (`cash_delta` netted only costs) | Sells silently destroyed capital; `agent_0001` short exactly $220.00 | Credit gross proceeds, then charge costs |
| 2 | Add-on BUY excluded costs from basis | Basis understated on every add | Blend `quantity × exec_price` |
| 3 | Stop-loss/take-profit exits filled at **$1.00** | Any exit would have sold the whole position for a dollar | Pass the triggering market price |
| 4 | 540/550 agents carried stale marks | Equity and drawdown drifted from the market by ~1.9% | `mark_symbol_to_market()` per tick |
| 5 | `paper_trading.db` never backed up | Total loss of trading history on disk failure | Separate verified backup + retention |
| 6 | Drawdown contradicted the ledger (`agent_0001` 40.24%, implied trough $311.96 vs ledger minimum $500.00) | False risk signal on the dashboard | Ledger-replay repair + boundary test |
| 7 | `status.py` hardcoded 4 service names | Two dead services reported HEALTHY | Enumerate `services.json` |
| 8 | JupyterHub API token embedded in served files | Full single-user API access to anyone reading the page | Removed; token rotated |
| 9 | `/api/providers/status` hardcoded "no live provider" | Endpoint contradicted the database it describes | Derive from attestation + stored bars |
| 10 | Dashboard tables unnamed, status not announced | Unusable structure for screen readers | ARIA labels, live region, hidden `h1` |

Performance work accompanied this: batching the tick into one transaction and
replacing per-order metric refreshes took a tick from **18.5 s to ~3 s** on this
network filesystem, which is what removed the health-check stalls.

Test coverage added: 22 tests in `test_paper_trading.py`, plus updated
provenance and provider-status contracts.

---

## 4. Blocked — needs an external party

These are real prerequisites I cannot satisfy from inside this container. They
are **not** marked passed.

| Gate | What is missing |
|---|---|
| **ACC-029 / EXT-01** — real cloud S3 restore | No cloud endpoint, bucket or credentials. Local encryption + restore drill passes. |
| **ACC-030 / EXT-02** — real host install & restart drill | Host has no systemd/Docker/root; PID 1 is `tini`. A non-privileged SIGKILL drill passes. |
| **ACC-031 / EXT-03** — independent security review | No external reviewer or signed go/no-go. Internal audit passes. |
| **G1** — TLS issuance/scan | No real certificate or scan; template only. |
| **G2** — network segmentation | Loopback listeners and preflight pass; no host-level segmentation. |
| **G3** — ingress hardening | nginx limits/CSP pass; no deployed public ingress. |
| **G4** — independent sign-off | Same as ACC-031. |
| **G5** — licensed market-data / legal review | Public `binance-public` bars are in use under exchange public-API terms. No legal approval for redistribution. |
| **G6** — host recovery drill | Container recovery evidence passes; host drill is EXT-02. |

Also operator-supplied, not code: an LLM provider key and a licensed
market-data contract, if those capabilities are wanted beyond research defaults.

---

## 5. Known limitation (recorded, not hidden)

39 legacy positions in AAPL, MSFT, GOOG and TSLA remain from a superseded symbol
configuration. They are frozen at cost (`current_price == avg_entry`), so they
contribute **exactly 0.00** unrealized P&L and do not inflate equity or
drawdown. They have no live feed and cannot be independently priced. They were
left in place deliberately rather than deleted, because deleting trade history
to make a report look cleaner is worse than showing a labelled legacy row.

The four active symbols (BTCUSD, ETHUSD, SOLUSD, BNBUSD) are fully live and
marked to market with zero drift.

---

## 6. Reproducing this

```sh
# status
/home/jovyan/.market-mind-ops/supervision/status.py          # exit 2 on CRITICAL
/home/jovyan/.market-mind-ops/supervision/status.py --json

# tests, exactly as CI runs them
cd /home/jovyan/-MARKET-MIND-AI
env -u MARKET_MIND_API_TOKEN PYTHONPATH=backend \
  .venvs/backend/bin/python -m unittest discover -s backend/tests

cd frontend && npm test && npm run test:ui && npm run build

# ledger reconciliation
# (replay paper_trades against paper_portfolios; expect 0 mismatches, delta 0)
```

## 7. Bottom line

The locally provable work is done and the evidence is in this repository. The
paper-trading engine now accounts for money correctly, marks positions at the
real market, backs up the only copy of its history, and reports its own health
truthfully. The remaining nine items are external approvals and infrastructure
that no amount of local work can substitute for.
