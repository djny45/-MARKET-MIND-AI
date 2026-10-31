# Deep Analysis Guide

The terminal's `--deep` option combines existing deterministic chart research with explicit stored-bar quality diagnostics and a compact consolidated dashboard summary.

## Commands

Run from `backend/`:

```bash
PYTHONPATH=. python terminal_chart_report.py --symbol BTCUSD --mode single --interval 1h --limit 500 --deep
PYTHONPATH=. python terminal_chart_report.py --symbol BTCUSD --mode multi --intervals 15m,1h,4h,1d --limit 500 --deep
PYTHONPATH=. python terminal_chart_report.py --symbol BTCUSD --mode single --interval 1h --limit 500 --deep --breadth-symbols ETHUSD,SOLUSD
```

Supported intervals are `15m`, `1h`, `4h`, and `1d`. Multi-timeframe output only compares intervals with enough stored observations; it never interpolates missing bars.

## Included research

- Moving-average regime, RSI, MACD, Bollinger Bands and ATR.
- Recent range references, candle-geometry labels and confirmed swing points.
- Per-timeframe quality checks for duplicate timestamps, invalid timestamps, non-increasing timestamps, inconsistent OHLC values, negative volume and missing required fields.
- Counts grouped by source and observation status, plus available retrieval timestamps.\n- Relative volume against an inclusive trailing window, return volatility per observation, descriptive volatility bands, and historical close-to-close maximum drawdown.\n- Optional cross-asset Pearson correlation using exact timestamp matches between close-to-close return series, including paired sample counts.\n- Historical price-level clusters formed from repeated confirmed swing highs and lows, with configurable percentage tolerance and minimum touch count.
- Coverage summary identifying intervals with insufficient stored bars.
- A consolidated `dashboard` section summarizing timeframe snapshots, data-quality counts, historical price-cluster counts, optional correlation pairs, and latest breadth observation.

## Historical price-level clusters\n\nEach timeframe deep report groups confirmed swing highs and swing lows into separate historical price clusters. The default tolerance is 0.5% and the minimum cluster size is two confirmed pivots. Clusters report their mean, observed price range, touch count, timestamps and indices. These are historical price concentrations, not guaranteed support/resistance or future targets. The swing detector excludes pivots without the required right-side confirmation bars.\n\n## Cross-asset comparison\n\nAdd `--correlate-symbols ETHUSD,SOLUSD` to a deep single-timeframe command. The primary `--symbol` is included automatically; at most 12 total symbols are accepted. Correlation uses exact timestamp intersections and the first selected interval in multi-timeframe mode. Missing pairs or constant series produce null values rather than invented estimates.\n\n## Historical market breadth\n\nAdd `--breadth-symbols ETHUSD,SOLUSD` to a deep report. The primary `--symbol` is included automatically; at most 30 total symbols are accepted. Breadth is calculated from each symbol’s consecutive stored closes, grouped only at exact matching return timestamps. Each observation reports coverage, advancing/declining/unchanged counts and percentages, and net advances. Timestamps below the two-symbol minimum coverage are omitted. No bars are interpolated and no exchange-calendar freshness is inferred.\n\n## Consolidated dashboard\n\nEvery deep report includes a `dashboard` object. It summarizes only the report sections already calculated: timeframe availability, latest stored bar references, moving-average regime, RSI/ATR, data-quality counts, historical cluster counts, optional correlation pairs and latest breadth. Unavailable inputs remain null or explicitly unavailable. The dashboard does not fetch new data and does not infer freshness.\n\n## Interpretation and limits

Correlation is historical co-movement, not causation; it can vary across samples and does not establish diversification or forecast future relationships. Breadth depends on the supplied symbol universe and data coverage; it is not a market-wide census or a directional recommendation.\n\nVolume and volatility diagnostics are descriptive. Relative volume uses the latest bar divided by the inclusive trailing average; volatility is reported per observation without annualization; drawdown uses closing prices only. Volatility bands use fixed thresholds and are not calibrated across asset classes.\n\nThe quality status means only that the implemented structural checks did or did not find issues. It does not certify data accuracy, source authenticity, licensing, or completeness. Retrieval timestamps are shown, but no freshness verdict is inferred. Missing bars are not labelled as errors because exchange calendars, trading sessions and provider schedules differ.

This is a historical descriptive research feature. It does not produce forecasts, directional signals, investment recommendations, or orders. Execution remains disabled.


## Interactive chart workspace

The frontend Research tab can load stored OHLCV history for a selected symbol and timeframe through `/api/market-data/history`. When stored bars are available, the chart renders timestamped candlesticks and displays the source/status labels returned by the stored observations. The user can select a confirmed historical swing-high or swing-low cluster from the deep report; the chart overlays its mean price and the panel displays the observed range, touch count and pivot timestamps. This overlay is a historical reference only. If no stored history exists, the chart does not fabricate bars; the existing manual/synthetic demo series remains separately labelled.


## Historical event timeline

The API endpoint `GET /api/research/timeline?symbol=BTCUSD&interval=1h&limit=200` returns the latest timestamped stored-bar observations (maximum 1,000). Each event includes OHLCV, close-to-close percentage change, source, status, retrieval timestamp, and any rule-based candle geometry or confirmed swing-point labels. The Research panel displays the latest 40 events in reverse chronological order. Empty stored history is explicitly reported; no missing observations are fabricated. Swing labels require right-side confirmation bars and therefore appear only after confirmation. This timeline is historical and descriptive, not a prediction or trading instruction.


### Historical indicator context

Each timeline event includes the indicator values calculated at that historical bar: SMA(20), RSI(14), and MACD (line, signal, histogram). RSI is aligned to the close-to-close return ending at the event bar. Values are calculated over the complete stored history before the requested display window is sliced. Warm-up values are null until sufficient observations exist; the UI displays these as insufficient history rather than zero. These are descriptive historical calculations, not predictions or instructions.


## Exact-timestamp multi-timeframe indicator comparison

When at least two intervals are requested, the deep report includes `cross_timeframe.aligned_indicator_comparison`. It intersects the exact stored timestamp strings present in every analyzed timeframe and reports the latest shared observation with independently calculated SMA(20), RSI(14), and MACD values. The shared timestamp count and alignment status are included. No interpolation, forward-fill, nearest-neighbour matching, or inferred bar alignment is performed. If there is no exact overlap, the latest comparison remains null and the status explains why. Indicator warm-up values remain null when insufficient history exists.


## Synchronized historical event markers

Selecting an event in the Research timeline now places a marker on the matching timestamp in the stored OHLCV candlestick chart. Matching uses the chart's normalized timestamp resolution; if the selected timestamp is not present in the loaded chart history, no marker is drawn. Changing the selected event updates or clears the marker. The marker is a navigation aid for historical inspection only.


## Market-data ingestion validation

The normalized market-data batch contract now trims and uppercases symbols, restricts intervals to the supported research set (15m, 1h, 4h, 1d), requires timezone-aware observation and retrieval timestamps, validates positive OHLC prices and nonnegative volume, and rejects duplicate timestamps within a batch. Storage sorts accepted bars chronologically before idempotent upsert and returns the stored timestamp span and an explicit ordering/duplicate summary. Source, status and retrieval timestamps remain attached to every observation. These checks validate structure, not provider authenticity, licensing, completeness or freshness.


## Historical CSV import

The API accepts user-supplied historical OHLCV CSV data at `POST /api/market-data/import-csv`. Required headers are `timestamp,open,high,low,close,volume`; timestamps must include a timezone. The importer enforces a 2 MB payload limit, 5,000-row limit, supported intervals (15m, 1h, 4h, 1d), finite/valid OHLCV values through the normalized Pydantic contract, and unique timestamps. A malformed row rejects the entire import with its CSV row number. Accepted rows are labelled `historical`, retain the supplied source label and retrieval timestamp, and are sorted chronologically by storage. Warnings make clear that user-supplied source authenticity/licensing is not independently verified and missing intervals are not inferred.

Example JSON body:

```json
{
  "symbol": "BTCUSD",
  "interval": "1h",
  "source": "my-historical-export",
  "csv_text": "timestamp,open,high,low,close,volume\\n2026-01-01T00:00:00Z,100,105,99,103,1200"
}
```


## Historical spacing and robust outlier diagnostics

The endpoint `GET /api/research/data-quality?symbol=BTCUSD&interval=1h&limit=500` provides a focused review of stored observations. For supported intervals (15m, 1h, 4h, 1d), it reports timestamp deltas greater than 1.5 times the nominal interval. These are elapsed-time spacing anomalies only: exchange sessions, holidays and provider schedules are not modelled, so a gap is not automatically a missing-candle error.

Close-to-close returns and volume observations receive a robust median/MAD outlier screen when at least 20 valid observations exist. The threshold is six scaled MADs. A zero-MAD sample is explicitly marked unavailable. Results identify original bar indices and never insert or estimate missing observations. Statistical flags are prompts for source-data review, not proof of corruption, forecasts, or trading signals.


Quality outlier flags now include evidence fields: original bar index, timestamp, measured value, robust MAD deviation, and (for return outliers) the prior close and prior timestamp. Timestamp-spacing flags include both endpoint timestamps. The frontend displays a short sample of these exact observations; the complete response remains available from the API. This improves auditability without changing the statistical threshold or inferring missing observations.


## Timestamp integrity diagnostics

The historical data-quality response also reports timezone-aware timestamp integrity checks: invalid or naive timestamps, duplicate instants (including equivalent instants written with different UTC offsets), and out-of-order observations. Each flag includes original bar indices and timestamp values. The diagnostics do not sort, delete, repair, or fabricate bars; they describe the supplied sequence so the caller can review the original data.


## Cross-source historical comparison

The endpoint `GET /api/research/source-comparison?symbol=BTCUSD&interval=1h&limit=500` groups stored observations by exact timezone-aware UTC instant and compares timestamps represented by at least two distinct sources. It reports each source's original OHLCV values, status, retrieval timestamp and timestamp string, plus min/max/spread per field. Equivalent instants expressed with different UTC offsets are aligned. Same-source duplicate instants and invalid timestamps are disclosed. The comparison does not rank providers, choose a preferred value, overwrite observations, infer missing bars, or certify source accuracy.


### Numeric field integrity in source comparisons

Each OHLCV field range includes valid, missing and invalid value counts. Non-numeric and non-finite values are retained in source observations and listed as invalid evidence, but excluded from min/max/spread calculations. Missing fields are counted separately. A spread is null when fewer than one valid value is available; no value is imputed.


## Downloadable research evidence bundle

The endpoint `GET /api/research/export?symbol=BTCUSD&interval=1h&limit=500` returns a downloadable JSON file named for the selected symbol and interval. The bundle contains the stored OHLCV observations with per-observation source, status and retrieval timestamps; a scope summary; timestamp, spacing and robust outlier diagnostics; exact-UTC cross-source comparisons; the historical event timeline; and explicit methodology limitations. The export preserves the observations as stored and does not rank providers, infer missing bars, or certify source authenticity. Empty history can be exported as an empty evidence bundle. The endpoint accepts only supported intervals and limits between 1 and 5,000 observations.



## Downloadable research evidence bundle

The Research dashboard provides a JSON download through `GET /api/research/export?symbol=BTCUSD&interval=1h&limit=500`. Schema version 1.1 retains the selected stored observations, per-observation provenance, timestamp integrity and spacing diagnostics, robust outlier results, exact-time source comparisons, and the descriptive event timeline. Empty history is exportable and remains explicitly empty.

The bundle includes a SHA-256 integrity digest over the complete canonical JSON bundle excluding the integrity field itself. To verify it, remove the `integrity` property, serialize the remaining object as UTF-8 JSON with sorted keys and compact separators, and compute SHA-256 over those bytes. This detects accidental changes after export; it does not authenticate the data provider, certify licensing, or prove when the observations were created. The export contains historical evidence only and no forecasts, directional recommendations, or orders.



### Verify an exported evidence file locally

From the repository root, run:

```bash
PYTHONPATH=backend python backend/verify_research_export.py ./BTCUSD-1h-research-evidence.json
```

The verifier prints a JSON result and exits with code 0 when the digest matches, 1 when the bundle or digest is invalid, and 2 when the file cannot be read or parsed. It checks accidental modification of the exported JSON, including observations and provenance. A matching digest is not a digital signature: it cannot prove who supplied the source data or prevent someone from editing the file and recomputing its digest.


To also save a detached verification record, pass `--report`:

```bash
PYTHONPATH=backend python backend/verify_research_export.py ./BTCUSD-1h-research-evidence.json --report ./BTCUSD-verification.json
```

The report records the verification timestamp (UTC), input filename, byte size, SHA-256 hash of the exact downloaded file, and the verification result. A failed digest still produces a report (and a non-zero exit status), so failed checks can be retained for audit. Keep the original evidence file and verification report together; the report itself is not digitally signed.


For multiple exports, pass two or more files. The command checks every file even if one is unreadable or has a mismatched digest, then returns a consolidated result. It exits with code 0 only when every file verifies; otherwise it exits with code 1 (verification/read error) or 2 for a report-writing/argument error.

```bash
PYTHONPATH=backend python backend/verify_research_export.py ./BTCUSD-1h-research-evidence.json ./ETHUSD-1h-research-evidence.json --batch-report ./batch-verification.json
```

The batch report records the UTC check time, file names, exact-file hashes, file sizes, individual verification outcomes, and aggregate valid/invalid counts. It does not embed the original evidence contents.
