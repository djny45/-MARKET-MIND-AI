# REMAINING WORK — evidence-based (2026-11-22)

This file records work that is **not** complete, with evidence. Nothing here is
claimed as delivered.

## 1. Public exposure gates — BLOCKED (external)
TLS ingress, network segmentation, independent penetration test and formal
security review are operator/external responsibilities. Server-side authz,
session/CSRF hardening, strict env validation, audit aggregation, headers and
distributed rate limiting are implemented (see `SECURITY_AUDIT.md`). No public
deployment is authorized.

## 2. Trivy CI scope — BLOCKED (OAuth permission)
Local Trivy 0.76.2 `fs --scanners vuln,misconfig,secret --severity MEDIUM,HIGH,CRITICAL .`
is clean. The CI job in `.github/workflows/quality.yml` still uses
`scanners: vuln,secret` and `severity: HIGH,CRITICAL`; adding misconfiguration
and MEDIUM findings requires a workflow change. `gh pr merge 76` failed with
`refusing to allow an OAuth App to create or update workflow ... without workflow scope`.
Remedy: owner runs `gh auth refresh -h github.com -s workflow` and completes
the device-code approval, then merge #76 and update the Trivy step.

## 3. Multi-host task execution — NOT IMPLEMENTED (intentional)
`docker-compose.yml` runs one backend + one supervisor on one SQLite volume;
`QueueCapabilities().multi_host_supported == False`. `backend/app/distributed_queue.py`
is a contract only. No broker, no multi-host integration test, no claim of
multi-host support. See `docs/ARCHITECTURE_DECISIONS.md` ADR-001.

## 4. Licensed live/delayed market data — NOT CONFIGURED (intentional)
`DataLicensingGate` blocks unauthorized sources; providers remain pending
manual license review. `provider_health.py` reports freshness/health without
external calls. No statement about current market prices is permitted. ADR-002.

## 5. Frontend coverage gaps — PARTIAL
109 frontend tests pass (10 node:test, 99 Vitest/jsdom). There is **no**
authentication UI, screener or heatmap component on `main`, so those requested
tests cannot target real code (`docs/FRONTEND_TESTING.md`,
`frontend/tests/ui/coverage-gaps.test.ts`). The Help (`?`) button in `App.tsx`
still has no handler; `loadNews` ignores `response.ok`; watchlist refresh has
no busy state; computed responsive layout needs a real browser. See the same
document for the full list.

## 6. Host-specific operations — PARTIAL
Executed locally with evidence in `docs/BACKUP_RECOVERY_DRILL.md`: verified
backup/restore, retention, off-host hook, resume, stale-lock recovery,
migration rollback, restart recovery, webhook alerting. Not run: cron/systemd
installation, Docker volume restore (`docker` absent), real S3 target,
production process-kill drill.

## 7. Pull requests — mostly reconciled
Merged after CI verification: #5, #6, #7, #9, #75. Closed with evidence:
#1, #4, #11, #27, #31, #35, #37, #45, #77.
Still open: #76 (workflow-scope blocked), #40 (screener/heatmap re-port needed),
#39 (durable-queue ADR partly superseded), #38 (lease-loss redesign needed),
#8 (ownership fencing needs narrow rebase). None were merged unreviewed.

## 8. CI for the final commits — PASS
[run 45057999583](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/45057999583)
passed all five jobs on the final commit `4abfa3da`. Docker Compose validation
is CI-authoritative because `docker` is absent locally. The only CI failure
encountered during this mission (Vitest 2.x advisories) was fixed by a real
dependency upgrade, not by weakening the audit gate.

## 9. Imported execution code — INTENTIONALLY INERT
AutoHedge signing/order modules, FinceptTerminal and Freqtrade live-bot code
remain reference-only; never imported, built or executed. Camofox browser is
localhost-only with no credentials. ADR-003.

## 10. Explicitly excluded from scope
Live brokerage execution, autonomous live trading, wallet private keys,
transaction signing, live order routing and market-making execution.
