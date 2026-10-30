# Quantitative algorithm catalogue

## Implemented deterministic indicators
The current dependency-light module implements SMA, EMA, returns, RSI, MACD, Bollinger Bands and realized volatility. Unit tests are included for these calculations.

## Candidate research modules
- Trend: WMA, VWAP, anchored VWAP, ADX/DMI, Aroon, Ichimoku, Donchian and Keltner channels.
- Momentum: stochastic oscillator, CCI, ROC, Williams %R, rolling z-scores.
- Volatility: true range, ATR, Parkinson and Garman-Klass estimators, drawdown, downside deviation, historical VaR and expected shortfall.
- Microstructure: spread, depth imbalance, trade imbalance, volume delta, liquidity concentration and quote/trade sequence checks. These require suitable authorized tick/depth data; OHLCV cannot reconstruct them reliably.
- Statistical: rolling correlation/covariance, cointegration, stationarity, PCA/factor exposure, beta, regime and change-point diagnostics.
- Event research: corporate actions, macro releases, event studies and surprise analysis.
- Candles and structure: doji, engulfing, hammer, shooting star, swing structure and volatility-adjusted breakouts.

Candidate modules are not represented as implemented. Each requires exact formulas, tests, warm-up and missing-data behavior, numerical stability checks, documentation and benchmark results. Hypotheses require out-of-sample evaluation and multiple-testing controls.
