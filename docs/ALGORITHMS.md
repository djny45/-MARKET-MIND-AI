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

## Historical performance-statistic input contract

The descriptive performance module accepts finite, strictly positive price observations. A supplied benchmark must also contain at least three finite, strictly positive prices and have the same number of return observations as the primary series. The optional risk-free rate must be finite; optional annualization periods must be finite and positive. Invalid inputs and derived values that exceed finite floating-point precision raise `ValueError` rather than allowing NaN or infinity to contaminate the report.

Annualized values are mathematical rescalings based on the caller-supplied observation frequency. The module does not infer frequency, align independently timestamped series, account for fees or corporate actions, or establish predictive value. Outputs remain historical descriptive statistics, not forecasts or recommendations.

## Indicator numeric-input contract

All deterministic indicator functions reject NaN and infinite observations. Derived return series and reported indicator values are checked for finite floating-point results before they are returned. Moving-average accumulation, return ratios and volatility calculations that exceed supported numeric precision fail with `ValueError` instead of emitting non-finite values. Realized-volatility annualization must be finite and positive. These guards improve numerical hygiene; they do not replace timestamp alignment, data-quality checks or independent validation of source observations.

## Market-diagnostics numeric boundary

The OHLCV market-diagnostics summary requires finite positive closes and finite non-negative volumes. Missing or invalid raw fields return `status=invalid_data`. If finite inputs produce an unrepresentable return, variance, volatility or relative-volume result, the function returns `status=numeric_overflow` with a limitation message instead of emitting non-finite JSON numbers. These are data-quality and numeric-safety outcomes, not market classifications.
