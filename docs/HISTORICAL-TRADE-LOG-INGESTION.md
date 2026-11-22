# Historical Trade-Log Intake Plan

This plan extends the existing historical market-data CSV importer. It does not introduce a second OHLCV store and does not imply that a trade-log archive has been received.

## Existing importer findings

The current `backend/app/csv_import.py` accepts UTF-8 CSV text up to 2 MB and 5,000 rows, requires timestamp/open/high/low/close/volume, requires timezone-aware timestamps, rejects duplicate normalized headers, malformed row widths, non-finite values and invalid bars, and sorts accepted bars chronologically. `backend/app/market_store.py` persists normalized bars in SQLite and writes batch audit events.

The existing API request model in `backend/app/main.py` caps `csv_text` at 2,000,000 characters. This is not an archive ingestion interface for a ~37 MB dataset.

## Required extension for large historical archives

1. Add an authenticated multipart upload endpoint with a strict total byte cap configurable by deployment policy. Stream to a quarantine directory outside the Git worktree; never load the entire archive into memory.
2. Compute SHA-256 while streaming. Record original filename as untrusted metadata, exact byte count, detected format, upload timestamp, and content hash. Do not trust extensions or archive member paths.
3. Permit only documented text formats initially (CSV and optionally gzip-compressed CSV). Reject encrypted archives, nested archives, path traversal, symlinks, oversized decompressed content, excessive compression ratios and unsupported file types.
4. Inspect headers and a bounded sample first. Map source columns through an explicit user-reviewed mapping; do not guess ambiguous columns or assume an execution log is OHLCV.
5. Parse rows incrementally with bounded batch sizes, decimal-safe numeric parsing, timezone validation, stable source-row identifiers and per-row quality outcomes.
6. Store raw source bytes in immutable quarantine storage; normalized rows and import manifest are separate. A failed import must not activate a partial dataset.
7. Use idempotency keyed by content hash plus parser/schema version. A repeat import returns the existing manifest rather than duplicating records.
8. Create an import manifest with hash, size, format, schema, parser version, total rows, accepted rows, rejected rows, duplicate rows, timestamp range, instrument counts, quality warnings and final state.
9. Make list/read/diagnostic APIs authenticated and read-only. Provide deletion and retention controls with an audit record; never expose raw secrets if unexpected columns contain credential-like content.
10. Add tests for chunk boundaries, malformed encoding, large row counts, decompression limits, archive traversal, partial failure rollback, duplicate import, hash stability, secret redaction and restart recovery.

## Important distinction

A trade log may contain order lifecycle events, fills, fees and balances rather than OHLCV bars. Keep it in a separate normalized event schema and do not force it into `market_bars`. Discover the actual file structure before designing the final mapping.

## Input still required

The approximately 37 MB archive has not been supplied in this conversation or verified in the repository. Do not claim ingestion or validation until the actual bytes are received.


## First-phase event-log schema and safeguards

A first usable normalized event contract can be defined without binding to a venue-specific CSV layout:

| Field | Type | Required | Meaning |
|---|---|---:|---|
| event_id | string | yes | Stable source event identifier; deterministic row fallback only when documented |
| event_time | ISO-8601 UTC | yes | Event timestamp, normalized to UTC |
| instrument | string | yes | Market or instrument identifier |
| event_type | enum | yes | ORDER_CREATED, ACKNOWLEDGED, PARTIAL_FILL, FILL, CANCELLED, REJECTED, EXPIRED, FEE |
| side | enum/null | conditional | BUY, SELL or null for non-side events |
| quantity | decimal/null | conditional | Positive event quantity, null when not applicable |
| price | decimal/null | conditional | Positive event price, null when not applicable |
| fee | decimal/null | no | Non-negative fee |
| fee_currency | string/null | no | Fee denomination |
| order_reference | string/null | no | Source order correlation key |
| source_row | integer | yes | Original 1-based source row reference |

Importer must preserve the original source row, distinguish missing from malformed fields, and record all rejected-row reasons. Do not assume that the user's archive uses this contract: first inspect file name, format, encoding, headers and a redacted sample. Never commit the archive itself.

## Import sequencing

1. Verify the received archive's SHA-256 and byte size; retain source bytes unchanged in quarantine.
2. Detect format and encoding; reject unsupported/binary content rather than guessing.
3. Inspect headers and a small redacted sample, then map source columns explicitly.
4. Parse incrementally with strict file and row limits, decimal-safe numeric parsing and UTC timestamp validation.
5. Produce a dry-run manifest with accepted/rejected counts, duplicates, timestamp range and reason codes.
6. Only after manifest review, persist as a separate immutable event dataset in a transaction.
7. Re-import of identical bytes + schema mapping must be idempotent; changed mapping version must create a distinct import version.
8. Keep event data separate from OHLCV bars; no event row may be silently converted into a candle.

