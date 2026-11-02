"""Stooq daily CSV adapter for historical research.

Stooq is a best-effort provider. Availability, access requirements, and terms can
change; callers must preserve source/freshness metadata and respect redistribution
restrictions. This adapter is not a real-time feed or execution-grade source.
"""
from __future__ import annotations

import asyncio
import csv
import io
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from typing import Optional

from .market_data import DataStatus, MarketDataBatch, OHLCVBar


class StooqAdapter:
    """Fetch daily OHLCV CSV from Stooq; API key is optional/configurable."""

    name = "stooq-daily-csv"

    def __init__(self, timeout_seconds: float = 10.0, api_key: Optional[str] = None):
        if not 1 <= timeout_seconds <= 30:
            raise ValueError("timeout_seconds must be between 1 and 30")
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key if api_key is not None else os.getenv("STOOQ_API_KEY")

    async def get_bars(
        self, symbol: str, interval: str = "1d", limit: int = 100
    ) -> MarketDataBatch:
        symbol = symbol.strip().lower()
        if not symbol or len(symbol) > 32:
            raise ValueError("symbol must contain 1 to 32 characters")
        if interval != "1d":
            raise ValueError("Stooq adapter supports daily bars only (1d)")
        if not 1 <= limit <= 5000:
            raise ValueError("limit must be between 1 and 5000")

        body = await asyncio.to_thread(self._fetch_csv, symbol)
        bars = self._parse_csv(body)
        bars = bars[-limit:]
        if not bars:
            raise ValueError(f"No valid daily OHLCV rows returned by Stooq for {symbol}")
        return MarketDataBatch(
            symbol=symbol.upper(),
            interval="1d",
            status=DataStatus.HISTORICAL,
            source=self.name,
            retrieved_at=datetime.now(timezone.utc),
            bars=bars,
            warnings=[
                "Stooq historical daily CSV; provider access, coverage, and terms may change.",
                "Historical research only; not a live feed or execution-grade data.",
                "Check Stooq licensing/redistribution restrictions before storing or republishing data.",
            ],
        )

    def _fetch_csv(self, symbol: str) -> str:
        params = {"s": symbol, "i": "d"}
        if self.api_key:
            params["apikey"] = self.api_key
        url = "https://stooq.com/q/d/l/?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(
            url, headers={"User-Agent": "MARKET-MIND-AI historical research adapter/1.0"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read(8_000_000)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Stooq returned HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"Stooq request failed: {exc}") from exc
        try:
            return raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise RuntimeError("Stooq returned non-UTF-8 CSV") from exc

    @staticmethod
    def _parse_csv(body: str) -> list[OHLCVBar]:
        text = (body or "").strip()
        if not text:
            return []
        lowered = text.lower()
        if not lowered.startswith("date,"):
            if "apikey" in lowered or "api key" in lowered:
                raise RuntimeError("Stooq may require an API key; configure STOOQ_API_KEY")
            if "limit" in lowered or "quota" in lowered or "exceeded" in lowered:
                raise RuntimeError("Stooq access quota or request limit reached")
            if lowered.startswith("<") or "html" in lowered[:300]:
                raise RuntimeError("Stooq returned a non-CSV access/challenge page")
            if text.upper().startswith("N/D"):
                return []
            raise RuntimeError("Stooq response did not contain the expected Date CSV header")

        bars: list[OHLCVBar] = []
        reader = csv.DictReader(io.StringIO(text))
        required = {"Date", "Open", "High", "Low", "Close", "Volume"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise RuntimeError("Stooq CSV is missing required OHLCV columns")
        for row in reader:
            try:
                day = date.fromisoformat((row.get("Date") or "").strip())
                values = [float((row.get(key) or "").strip()) for key in ("Open", "High", "Low", "Close")]
                volume_text = (row.get("Volume") or "").strip()
                volume = float(volume_text) if volume_text else 0.0
                if any(value <= 0 for value in values) or volume < 0:
                    continue
                bars.append(OHLCVBar(
                    timestamp=datetime(day.year, day.month, day.day, tzinfo=timezone.utc),
                    open=values[0], high=values[1], low=values[2], close=values[3],
                    volume=volume,
                ))
            except (TypeError, ValueError, OverflowError):
                # Ignore malformed individual rows; reject the batch if nothing remains.
                continue
        bars.sort(key=lambda bar: bar.timestamp)
        # Remove duplicate dates deterministically (keep the last CSV occurrence).
        deduplicated = {bar.timestamp: bar for bar in bars}
        return [deduplicated[key] for key in sorted(deduplicated)]
