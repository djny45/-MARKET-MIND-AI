# Research Execution Sandbox Architecture

Status: design and acceptance contract only. This document does not enable brokerage connectivity, wallet access, private-key storage, transaction signing, order submission, or live trading.

## Objective

Provide a reproducible, non-custodial research boundary for evaluating execution concepts with synthetic fixtures and explicitly supplied historical datasets. Keep research outputs separate from any real account or venue.

## Components

- **Wallet security boundary:** do not ingest private keys, seed phrases, wallet exports, or signing credentials. Reject secret-like inputs; redact potentially sensitive values from logs; never write them to SQLite, telemetry, prompts, artifacts, or Git.
- **Transaction review fixtures:** accept only synthetic, non-broadcast transaction-shaped test objects. Validate schema, chain identifier, destination format, nonce/sequence, fee fields, expiry and replay identifiers. Test cases must prove that no signing or broadcast adapter exists in the runtime.
- **Execution simulator:** deterministic order-state model for NEW, ACKNOWLEDGED, PARTIALLY_FILLED, FILLED, CANCELLED, REJECTED, and EXPIRED. Require an explicit synthetic fill model. Track idempotency keys, event timestamps, fees, slippage assumptions, and error reasons. Never call a broker or exchange.
- **Market-making research:** pure calculations over caller-supplied order-book snapshots: freshness checks, crossed-book rejection, mid/spread, indicative quote calculations, inventory-skew sensitivity and synthetic fill arithmetic. No venue polling or order API payload generation.
- **Historical trade-log ingestion:** import only user-provided files. Discover formats before parsing; record SHA-256, byte count, source filename, import time, schema version, row counts, timestamp range, duplicate count and rejected-row reasons. Preserve the original file unchanged. Do not infer that data is available until the file is supplied.

## Data contract

Each normalized event should include source_id, dataset_sha256, event_id, instrument_id, event_time_utc, event_type, side, price, quantity, fee, fee_currency, venue_label (optional), and raw_record_reference. Use decimal-safe parsing for monetary and quantity fields. Reject non-finite values, invalid timestamps, unsupported units, malformed identifiers and conflicting duplicate event IDs. Missing fields remain null with an explicit quality flag; do not fabricate values.

## Required tests

1. Secret-like strings are rejected and never appear in captured logs or exception messages.
2. No private-key, seed phrase, signing, broker, exchange order, or broadcast dependencies are imported by the sandbox.
3. Simulator state transitions reject illegal transitions and duplicate idempotency keys.
4. Replaying identical fixture input produces identical normalized output and summary metrics.
5. Market-making calculations reject stale, crossed, negative, non-finite and future-dated books.
6. Historical ingestion produces stable hashes, row counts, UTC timestamp ranges and deterministic duplicate/rejection reports.
7. Import is transactional: a failed batch leaves no partial dataset active.
8. API routes remain authenticated and read-only for imported datasets; no mutation of source files.
9. CI runs backend tests, frontend tests/build, Docker integration, dependency audit and filesystem security scan.

## Operational gates

- Keep the product research-only and local/private.
- No secrets in repository or test fixtures.
- Keep the original historical archive outside Git; add only small synthetic fixtures.
- Document retention, deletion, backup and restore handling for imported datasets.
- Require independent review before expanding any security boundary.
