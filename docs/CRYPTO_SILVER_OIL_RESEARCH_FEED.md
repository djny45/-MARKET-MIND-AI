# Crypto, Silver and Oil Research Feed

The terminal already defines Crypto, Silver and Crude Oil desks. This collector
adds a repeatable historical-data ingestion path for the existing
`market_bars` research store.

## Coverage

| Desk | Platform symbol | Yahoo chart symbol |
|---|---|---|
| Crypto | BTCUSD | BTC-USD |
| Crypto | ETHUSD | ETH-USD |
| Silver | XAGUSD | SI=F |
| Oil | WTI | CL=F |
| Oil | BRENT | BZ=F |

## Run

From the repository root, with the backend Python dependencies installed:

```bash
python scripts/ingest_crypto_silver_oil_research.py --once
python scripts/ingest_crypto_silver_oil_research.py --poll-seconds 900
```

Set `MARKET_MIND_DB` to the intended SQLite research database path if the
default `./data/market_mind.db` is not the correct store. Keep the database
path and any credentials out of source control.

## Data integrity and limitations

- The adapter writes `HISTORICAL` observations with source
  `yahoo-finance-chart`; it never labels these observations LIVE or DELAYED.
- The 15-minute chart endpoint is best-effort, unofficial and subject to
  upstream availability, rate limits and provider terms. It is not a guaranteed
  real-time feed and is not execution-grade.
- `SI=F`, `CL=F` and `BZ=F` are continuous research-contract symbols, not a
  selected dated futures expiry and not MCX quotes.
- Each instrument is isolated: a provider error for one symbol does not block
  the remaining assets. Failures are reported as unavailable, never replaced
  with synthetic prices.
- Before redistribution, public display, or any live/delayed claim, complete
  the licensing and operator-attestation requirements in
  `docs/MARKET_DATA_LICENSING.md`.
- This collector does not place orders, create trading signals, or enable
  autonomous execution. It only appends provenance-labelled research bars.
