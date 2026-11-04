# Smart Money Concepts (SMC) research integration

MARKET-MIND-AI vendors the indicator implementation from
[joshyattridge/smart-money-concepts](https://github.com/joshyattridge/smart-money-concepts)
(version **0.0.27**, upstream commit
[1b62fd6c41e1f508e7ed76831a039fa4c82d42f6](https://github.com/joshyattridge/smart-money-concepts/commit/1b62fd6c41e1f508e7ed76831a039fa4c82d42f6)).
The upstream MIT license is retained beside the source at
`backend/app/vendor/smartmoneyconcepts/LICENSE`.

## Install optional research dependencies

From the repository root:

```bash
python -m pip install -r backend/requirements-smc-research.txt
```

These dependencies are intentionally separate from the core backend requirements.

## Offline use

`backend/app/smc_research.py` exposes
`analyze_historical_ohlcv(ohlc, ...)`. It validates OHLC columns and returns
indicator tables for Fair Value Gaps, swing highs/lows, BOS/CHoCH, order blocks,
liquidity, and retracements. The caller supplies the historical DataFrame; the
module does not fetch data or provide a broker/data-provider connection.

## Important methodology limitation

**This library contains retrospective calculations.** In particular, swing
high/low detection uses bars on both sides of a candidate. A historical chart
may therefore label a past candle using information that only became available
later. Some returned columns also include mitigation/broken indices. Do not
treat a marker at its plotted candle as information that was available then,
and do not use these outputs as a live signal or as evidence of predictive
performance. Any future evaluation must explicitly model information
availability, timestamps, data quality, and look-ahead bias.

## Scope

This is an offline indicator-research component only. It adds no brokerage
credentials, order routing, paper/live trading, automated execution, trade
recommendations, or profit claims. It is not investment advice.

The upstream project is licensed under MIT. Its license and copyright notice
must remain with the vendored source. See the upstream repository for its
complete documentation and history.
