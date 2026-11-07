"""Yahoo Finance chart endpoint adapter for historical research data.

This adapter is community-facing and best-effort, not an official Yahoo API.
It is rate-limited/provider-dependent and must not be treated as execution-grade
or guaranteed real-time data. It returns normalized bars only.
"""
from __future__ import annotations

import asyncio
import json
import math
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from .market_data import DataStatus, MarketDataBatch, OHLCVBar

_INTERVALS = {"15m": "15m", "1h": "1h", "4h": "1h", "1d": "1d"}
_PERIODS = {"15m": "5d", "1h": "1mo", "4h": "3mo", "1d": "5y"}


class YahooFinanceAdapter:
    """Fetch Yahoo chart OHLCV data without an API key; best-effort only."""

    name = "yahoo-finance-chart"

    def __init__(self, timeout_seconds: float = 10.0):
        if not 1 <= timeout_seconds <= 30:
            raise ValueError("timeout_seconds must be between 1 and 30")
        self.timeout_seconds = timeout_seconds

    async def get_bars(self, symbol: str, interval: str = "1d", limit: int = 100) -> MarketDataBatch:
        symbol = symbol.strip().upper()
        if not symbol or len(symbol) > 32:
            raise ValueError("symbol must contain 1 to 32 characters")
        if interval not in _INTERVALS:
            raise ValueError("interval must be one of 15m, 1h, 4h, 1d")
        if not 1 <= limit <= 5000:
            raise ValueError("limit must be between 1 and 5000")
        payload = await asyncio.to_thread(self._fetch_chart, symbol, interval)
        try:
            result = payload["chart"]["result"][0]
            timestamps = result.get("timestamp") or []
            quote = result["indicators"]["quote"][0]
            adjusted_close_values = (result.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose") or []
            bars = []
            for i, stamp in enumerate(timestamps):
                values = [quote.get(key, [])[i] if i < len(quote.get(key, [])) else None
                          for key in ("open", "high", "low", "close", "volume")]
                if any(value is None for value in values[:4]) or values[4] is None:
                    continue
                numeric = [float(value) for value in values]
                if not all(math.isfinite(value) for value in numeric):
                    continue
                open_value, high_value, low_value, close_value, volume = numeric
                if (min(open_value, high_value, low_value, close_value) <= 0
                        or volume < 0
                        or high_value < max(open_value, low_value, close_value)
                        or low_value > min(open_value, high_value, close_value)):
                    continue
                bars.append(OHLCVBar(
                    timestamp=datetime.fromtimestamp(stamp, tz=timezone.utc),
                    open=open_value, high=high_value, low=low_value,
                    close=close_value, volume=volume,
                    adjusted_close=(float(adjusted_close_values[i])
                                    if i < len(adjusted_close_values)
                                    and adjusted_close_values[i] is not None
                                    and math.isfinite(float(adjusted_close_values[i]))
                                    and float(adjusted_close_values[i]) > 0 else None),
                ))
        except (KeyError, IndexError, TypeError, ValueError, OverflowError, OSError) as exc:
            raise ValueError("Yahoo response did not contain valid OHLCV chart data") from exc
        if interval == "4h":
            # Yahoo exposes hourly bars for this range. Aggregate only complete,
            # UTC-aligned four-hour buckets; never label hourly bars as 4h.
            grouped = {}
            for bar in bars:
                bucket = int(bar.timestamp.timestamp()) // 14400
                grouped.setdefault(bucket, []).append(bar)
            aggregated = []
            for bucket in sorted(grouped):
                group = grouped[bucket]
                timestamps = [int(bar.timestamp.timestamp()) for bar in group]
                bucket_start = bucket * 14400
                if timestamps != [bucket_start + offset * 3600 for offset in range(4)]:
                    continue
                try:
                    aggregated_volume = math.fsum(bar.volume for bar in group)
                except (OverflowError, ValueError):
                    raise ValueError("aggregated four-hour volume must be finite") from None
                if not math.isfinite(aggregated_volume):
                    raise ValueError("aggregated four-hour volume must be finite")
                aggregated.append(OHLCVBar(
                    timestamp=group[0].timestamp,
                    open=group[0].open,
                    high=max(bar.high for bar in group),
                    low=min(bar.low for bar in group),
                    close=group[-1].close,
                    volume=aggregated_volume,
                    adjusted_close=group[-1].adjusted_close,
                ))
            bars = aggregated
        timestamps = [bar.timestamp for bar in bars]
        if any(current <= previous for previous, current in zip(timestamps, timestamps[1:])):
            raise ValueError("Yahoo chart timestamps must be unique and chronological")
        if interval == "4h":
            raise ValueError(f"No OHLCV bars returned for {symbol}; verify symbol and provider availability")
        return MarketDataBatch(
            symbol=symbol,
            interval=interval,
            status=DataStatus.HISTORICAL,
            source=self.name,
            retrieved_at=datetime.now(timezone.utc),
            bars=bars,
            warnings=[
                "Best-effort Yahoo Finance chart data; provider availability and licensing may change.",
                "Historical research data only; not guaranteed real-time or suitable for execution.",
                "4h bars are aggregated from complete UTC-aligned hourly bars; incomplete buckets are discarded.",
            ] if interval == "4h" else [
                "Best-effort Yahoo Finance chart data; provider availability and licensing may change.",
                "Historical research data only; not guaranteed real-time or suitable for execution.",
            ],
        )

    def _fetch_chart(self, symbol: str, interval: str) -> dict[str, Any]:
        encoded_symbol = urllib.parse.quote(symbol, safe="")
        query = urllib.parse.urlencode({
            "interval": _INTERVALS[interval],
            "range": _PERIODS[interval],
            "events": "history",
        })
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_symbol}?{query}"
        request = urllib.request.Request(url, headers={"User-Agent": "MARKET-MIND-AI research adapter/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read(8_000_000)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Yahoo Finance returned HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"Yahoo Finance request failed: {exc}") from exc
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Yahoo Finance returned invalid JSON") from exc
        chart_error = data.get("chart", {}).get("error")
        if chart_error:
            raise RuntimeError(f"Yahoo Finance chart error: {chart_error.get('description', 'unknown error')}")
        return data
