# Volume Indicator Research Module

MARKET-MIND-AI includes a dependency-light OHLCV volume-indicator module at
`backend/app/volume_indicators.py`. It accepts chronological bars (oldest first)
and calculates descriptive historical series only. It does not fetch market data,
generate orders, or connect to a broker.

## Included calculations

| Indicator | Description |
|---|---|
| OBV | On-Balance Volume |
| ADL | Accumulation/Distribution Line |
| Chaikin Oscillator | EMA spread of the A/D line |
| CMF | Chaikin Money Flow |
| MFI | Money Flow Index |
| Force Index | Price change multiplied by volume |
| Ease of Movement | Price movement scaled by volume and range |
| VPT | Volume Price Trend |
| NVI / PVI | Negative / Positive Volume Index |
| VWAP | Cumulative volume-weighted typical price |
| Relative Volume | Current volume divided by rolling average volume |
| Volume Oscillator | Fast/slow EMA spread of volume, as a percentage |
| Volume Rate of Change | Period-over-period volume percentage change |
| Volume SMA | Rolling average volume |

## API

`POST /api/indicators/volume`

Request JSON:

```json
{
  "high": [11, 12, 13],
  "low": [9, 10, 11],
  "close": [10, 11, 12],
  "volume": [100, 150, 180],
  "period": 20
}
```

All four arrays must have equal lengths, at least two observations, finite values,
and chronological ordering. OHLC values must be internally consistent and volume
must be non-negative. The API rejects invalid inputs with HTTP 400.

## Open-source reference projects

These projects are useful for cross-checking formulas, researching additional
indicators, and future compatibility work:

- [bukosabino/ta](https://github.com/bukosabino/ta) — Pandas/NumPy technical-analysis library; includes MFI, ADI, OBV, CMF, Force Index, EoM, VPT, NVI and VWAP.
- [pandas-ta-classic](https://github.com/xgboosted/pandas-ta-classic) — broader volume set including AD/ADOSC, AOBV, CMF, EFI, EOM, KVO, Market Facilitation Index, MFI, NVI/PVI, OBV, PVT, VFI, volume oscillator and volume profile.
- [DaveSkender/Stock.Indicators](https://github.com/DaveSkender/Stock.Indicators) — volume-related indicators including ADL, CMF, Chaikin Oscillator, Force Index, Klinger Volume Oscillator, MFI, OBV and PVO.
- [nardew/talipp](https://github.com/nardew/talipp) — incremental indicator library with ADL, Chaikin Oscillator, EoM, Force Index, KVO, OBV and VWAP.

The above are upstream references, not runtime dependencies. Their presence here
does not imply their code has been copied or installed. Check each project's
current license and version before vendoring or adding it as a dependency.

## Interpretation limits

Volume indicators are descriptive transformations of supplied OHLCV data. They
can disagree, are sensitive to data quality and bar construction, and do not
establish intent, future price direction, or a reliable outcome. Crypto venue
volume may be fragmented or incomparable across exchanges. Use provenance and
historical validation when comparing sources. This module is for educational
and historical research only; live market monitoring, brokerage access, and
financial transaction workflows are outside this feature's scope.
