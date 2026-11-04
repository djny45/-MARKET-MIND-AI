# MARKET-MIND AI Research Terminal 2026

A standalone, responsive HTML dashboard preview for the offline research workflow.

## Open the dashboard

Open `frontend/research-terminal-2026/index.html` directly in a modern browser. No npm install, server, API key, or network connection is required.

## UI sections

- **Overview:** synthetic chart, dataset cards, sample watchlist, feature coverage, and terminal activity.
- **Dataset Lab:** browser-local CSV picker for a small preview (up to 10 MB, first 12 columns and five data rows), plus commands to inspect files with the Python tools.
- **Indicator Matrix:** definitions and limitations for historical annotations.
- **Terminal Logs:** simulated read-only log console with a small allowlist of UI commands (`help`, `status`, `dataset`, `indicators`, `clear`).

## Important limitations

- Dashboard chart and sample instrument values are fabricated UI demo data. They are not real-time market data.
- The terminal accepts only its documented UI commands; it does not execute shell commands.
- The CSV picker reads only the file you explicitly select, in browser memory using FileReader; it does not upload or transmit it. The quick preview is intentionally basic (CSV quoting support, non-empty line count, limited rows/columns), not a replacement for robust OHLCV validation. Run the Python research utilities separately from the repository root for full validation and indicator analysis.
- No exchange/broker connections, forecasts, trade signals, or order execution are included.
- SMC swing annotations may use future bars and can introduce look-ahead bias.
