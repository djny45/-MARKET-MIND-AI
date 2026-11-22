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
