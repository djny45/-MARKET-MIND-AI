# Single-chart manual research workflow

MARKET-MIND-AI is a research and chart-review tool. This workflow is designed for a person to inspect historical or user-supplied data manually; it does not place orders or generate personalized investment advice.

## One-chart review

1. Select one instrument and one timeframe.
2. Load stored OHLCV history or clearly labelled synthetic/sample data.
3. Inspect the candlestick chart and volume histogram in the same chart panel.
4. Use the crosshair to inspect timestamps and price levels.
5. Review source, data status, and retrieval timestamp before interpreting the chart. Sample/synthetic data must never be mistaken for live market data.
6. If needed, enter hypothetical entry, stop, and target levels into the existing educational setup calculator. Treat its output as geometry only—not a recommended trade, validated strategy, or order instruction.
7. Record the reason for the review and the data source. Re-check the analysis against another timeframe or source rather than relying on a single chart.

## Manual review checklist

- [ ] Instrument and timeframe are correct.
- [ ] Data source and status are visible and understood.
- [ ] Timestamps are ordered and the OHLCV quality checks pass.
- [ ] Missing bars, gaps, and provider limitations are considered.
- [ ] Entry/stop/target levels, if entered, are hypothetical and user supplied.
- [ ] Any conclusions are written as uncertain research observations, not forecasts.

## Safety and implementation boundary

- No broker credentials, order routing, automatic order placement, or live-money execution.
- No unattended trade execution or auto-entry/exit.
- No “buy/sell” signal is produced by this manual workflow.
- The chart is a visual inspection aid. It does not guarantee data freshness, accuracy, profitability, or future outcomes.
- Historical and synthetic observations must remain explicitly labelled.
- Any future chart annotations should be user-entered review levels and should not silently become executable instructions.

## Existing implementation

- Frontend chart: [PriceChart.tsx](../frontend/src/PriceChart.tsx) — candlesticks, volume histogram, crosshair, and selected historical cluster marker/level.
- Research endpoint: `GET /api/research/chart` — descriptive report from stored bars.
- Educational setup endpoint: `POST /api/research/setup` — hypothetical setup geometry from user-supplied levels.
- Market data sample endpoint: `GET /api/market-data/sample` — synthetic fixture, not a live quote.

For local setup and data-source limitations, see [DEVELOPMENT.md](DEVELOPMENT.md) and [DEEP-ANALYSIS.md](DEEP-ANALYSIS.md).
