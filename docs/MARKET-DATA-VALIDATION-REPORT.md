# Market-data validation report

## Purpose

Use `app.market_data_validation.validate_market_data_payload` to convert an incoming market-data batch into a compact report suitable for review by an API or UI layer.

This is a **structural contract check**, not a provider trust score, trading recommendation, or guarantee of complete/fresh market data.

## Python usage

```python
from app.market_data_validation import validate_market_data_payload

report = validate_market_data_payload(
    payload,
    max_retrieval_age_seconds=300,  # optional caller-defined freshness threshold
)

if not report["valid"]:
    # Surface report["errors"] to the reviewer and stop downstream analysis.
    ...
else:
    # Continue with descriptive research only after review.
    ...
```

## Report fields

| Field | Meaning |
|---|---|
| `schema_version` | Report format version |
| `generated_at` | UTC time when the report was generated |
| `retrieved_at` | Batch retrieval timestamp (valid reports only) |
| `retrieval_age_seconds` | Difference between validation time and `retrieved_at`; a future timestamp remains negative so clock skew is visible |
| `retrieval_freshness` | `within_threshold`, `stale`, `future_timestamp`, or `null` when no threshold is supplied |
| `freshness_threshold_seconds` | Caller-supplied maximum retrieval age, or `null` when no threshold is supplied |
| `valid` | Whether the batch passed the MarketDataBatch contract |
| `result` | Machine-readable status: `valid` or `invalid` |
| `error_count` | Number of field-level validation errors |
| `bar_count` | Number of bars for valid payloads; null when invalid |
| `errors` | Field-level validation errors |
| `warnings` | Batch warnings preserved from the source contract |
| `limitations` | Explicit caveats about what validation does not establish |

## Integration guidance

- Keep validation at the boundary where raw provider data enters the application.
- Do not duplicate OHLCV schema checks in individual UI components.
- If `valid` is false, display the errors and prevent the payload from entering downstream analytics.
- Preserve `warnings` and `limitations` when presenting the report.
- Do not label a payload “verified” or “complete” based only on this report.
- Provider authenticity, licensing, and exchange-session completeness need separate evidence and checks.
- Freshness is only classified when the caller supplies `max_retrieval_age_seconds`; it is a caller policy threshold, not a universal market-data freshness standard.
- A future `retrieved_at` is reported as `future_timestamp` with a negative age and warning, rather than being clamped to zero or labelled fresh.
- The API accepts the same optional field alongside `payload` in `POST /api/market-data/validate`.
