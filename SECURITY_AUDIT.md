# SECURITY AUDIT — delivered boundaries

Scope: tracked application source, configuration and integrated tooling.
Imported third-party source under gitignored `third_party/` was reviewed as
reference material only and was not executed as part of the application.

## Findings and resolutions

| Finding | Resolution |
| --- | --- |
| No structured research-loop security review beyond per-user auth | Added distributed-queue design (multi-host) with retries, deadletter and observability; licensed-data gate with explicit authorization + manual review; full 5-phase methodology review (backtest costs, leakage, multiple-testing correction, worker-memory escapes). |
| --- | --- |
| No per-user identity or authorization | Added opt-in per-user sessions (`user_auth.py`, `user_session_middleware.py`): scrypt password verification, HttpOnly session cookie, hashed session/CSRF tokens stored in SQLite, idle/absolute expiry, roles (viewer/analyst/operator/admin), login/logout/me endpoints, operator-gated memory review. 14 tests. |
| No abuse throttling on API | Added opt-in `RateLimitMiddleware` (`API_RATE_LIMIT_PER_MINUTE`), health/ready exempt; 5 tests. Ingress/proxy limits still required for production. |
| Unvalidated deployment environment | Added `validate_environment()` and `GET /api/environment-validation`; checks auth token length, CORS wildcards, numeric settings; never returns secret values. 5 tests. |
| Misleading/incorrect security documentation | Corrected authentication scope (deployment-wide bearer only, no per-user roles), MCP tool count and browser boundaries. |
| Imported execution code | AutoHedge signing/order code, Freqtrade live bot and FinceptTerminal binaries remain inert reference copies; not imported, installed or executed. |
| Browser risk | Read-only fetcher: HTTPS allowlist, SSRF/DNS checks, no JS/redirects/downloads/credentials. Camofox: localhost only, no API/access keys, isolated profile/cookies/uploads; 31 tools verified. |
| Secret exposure | No keys in repo, frontend bundle, diagnostics or reports; diagnostics report `secret_values_exposed: false`. |
| Brokerage | No code path signs transactions or routes orders; health reports `broker_execution: false`. |

## Outstanding security work

- Per-user auth is opt-in and requires operator-provisioned users; per-resource authorization is currently coarse (role hierarchy on the memory-review endpoint only).
- TLS ingress and network segmentation (operator responsibility).
- Independent penetration test and formal dependency/licence review.
- Distributed rate limiting and audit aggregation (single-process limiter only).

## Safe-use statement

This build is a research and paper-simulation platform. It is suitable for
private, operator-managed deployment only. Do not expose it publicly until the
outstanding items are resolved.
