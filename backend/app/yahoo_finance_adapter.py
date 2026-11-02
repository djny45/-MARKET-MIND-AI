"""Yahoo Finance chart endpoint adapter for historical research data.

This adapter is community-facing and best-effort, not an official Yahoo API.
It is rate-limited/provider-dependent and must not be treated as execution-grade
or guaranteed real-time data. It returns normalized bars only.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from .market_data import DataStatus, MarketDataBatch, OHLCVBar

_INTERVALS = {"15m": "15m", "1h": "1h", "1d": "1d"}
_PERIODS = {"15m": "5d", "1h": "1mo", "1d": "1y"}


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
            raise ValueError("interval must be one of 15m, 1h, 1d; 4h aggregation is not supported")
        if not 1 <= limit <= 5000:
            raise ValueError("limit must be between 1 and 5000")
        payload = await asyncio.to_thread(self._fetch_chart, symbol, interval)
        try:
            result = payload["chart"]["result"][0]
            timestamps = result.get("timestamp") or []
            quote = result["indicators"]["quote"][0]
            bars = []
            for i, stamp in enumerate(timestamps):
                values = [quote.get(key, [])[i] if i < len(quote.get(key, [])) else None
                          for key in ("open", "high", "low", "close", "volume")]
                if any(value is None for value in values):
                    continue
                bars.append(OHLCVBar(
                    timestamp=datetime.fromtimestamp(stamp, tz=timezone.utc),
                    open=float(values[0]), high=float(values[1]), low=float(values[2]),
                    close=float(values[3]), volume=float(values[4]),
                ))
        except (KeyError, IndexError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Yahoo response did not contain valid OHLCV chart data") from exc
        bars = bars[-limit:]
        if not bars:
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
