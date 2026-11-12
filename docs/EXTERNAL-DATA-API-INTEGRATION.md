# External API integration boundary

## Purpose

Market Mind AI is a local, terminal-first research application. External API credentials are optional and are used only by explicitly configured data adapters. The application must remain useful with local fixtures and public/free data sources where their terms permit.

## Supported API use

Adapters may use narrowly scoped, read-only credentials to retrieve:

- Market quotes, historical bars and reference data.
- Fundamentals, corporate actions and market calendars.
- News, filings and other licensed research material.
- Account metadata only when it is strictly necessary for a read-only connectivity check.

A provider adapter must declare its supported endpoints, required scopes, rate limits, data delay, timestamp semantics and terms/licensing constraints. Normalize provider responses into the canonical data model and preserve source identifiers, retrieval timestamps and quality metadata.

## Credentials and local operation

- Keep credentials in local environment variables or an OS-backed secret store; never commit keys, tokens, account identifiers or credential files.
- Never expose secrets to the browser, specialist workers, prompts, logs, traces, workflow exports or research artifacts.
- Give each key the minimum read-only scope available. Do not request order, transfer, withdrawal or account-management permissions.
- Redact authorization headers, query-string secrets and token-like values from all errors and logs.
- Provide a connectivity test that reports provider name, granted read-only capabilities and last successful retrieval without printing credential material.
- If credentials are absent, invalid, expired or revoked, disable that adapter and continue in disconnected/local-data mode.

## Execution boundary

This repository is a research and analytics system. It does not implement brokerage order placement, order modification/cancellation, transfers, withdrawals or other financial execution. A connected API must not change that boundary. Do not add order endpoints, execution credentials, signing flows, broker order queues or autonomous execution agents to this project.

Signals and analytics are informational research outputs, not instructions to transact. Keep provider adapters and specialist agents read-only, and enforce the boundary server-side rather than relying on UI visibility.

## Acceptance checks for a new provider

1. The adapter is disabled by default and has no embedded credentials.
2. Tests prove that only documented read-only endpoints are called.
3. Tests prove that secrets are absent from logs, errors, API responses and persisted research records.
4. Missing or invalid credentials fail closed without breaking local research workflows.
5. Rate limits, stale data, provider outages and licensing metadata are surfaced to the user.
6. No broker order or funds-movement capability is present in the adapter contract.
