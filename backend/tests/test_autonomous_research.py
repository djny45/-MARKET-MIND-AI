from datetime import datetime, timezone

import pytest

from app.autonomous_research import run_autonomous_research
from app.market_discovery import MarketCandidate
from app.market_data import SyntheticFixtureAdapter


NOW = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)


def candidate(symbol="TEST"):
    return MarketCandidate(
        symbol=symbol, venue="FIXTURE", asset_class="equity", source="test",
        observed_at=NOW.isoformat(), data_available=True, data_quality=0.9,
        activity=0.8, volatility=0.4, news_attention=None, social_attention=None,
        timeframes=("1d",),
    )


@pytest.mark.asyncio
async def test_autonomous_loop_prioritizes_and_builds_descriptive_report():
    result = await run_autonomous_research(
        [candidate()], SyntheticFixtureAdapter(), now=NOW,
        intervals=("1d",), bars_limit=5,
    )
    assert result["mode"] == "autonomous_descriptive_market_research"
    assert result["research_queue_size"] == 1
    item = result["results"][0]
    assert item["symbol"] == "TEST"
    assert item["status"] == "completed"
    report = item["timeframes"]["1d"]
    assert report["mode"] == "descriptive_research_only"
    assert report["data_status"] == "synthetic"
    assert report["execution"] == "disabled"
    assert result["shared_ai_synthesis"]["status"] == "not_requested"


@pytest.mark.asyncio
async def test_candidate_generator_is_consumed_once_and_counted():
    candidates = (item for item in [candidate("ONE"), candidate("TWO")])
    result = await run_autonomous_research(
        candidates, SyntheticFixtureAdapter(), now=NOW,
        intervals=("1d",), bars_limit=5,
    )
    assert result["candidates_received"] == 2
    assert [item["symbol"] for item in result["results"]] == ["ONE", "TWO"]


@pytest.mark.asyncio
async def test_invalid_adapter_symbol_isolated_as_timeframe_error():
    class WrongSymbolAdapter:
        name = "wrong-symbol"

        async def get_bars(self, symbol, interval, limit):
            batch = await SyntheticFixtureAdapter().get_bars("WRONG", interval, 5)
            return batch

    result = await run_autonomous_research(
        [candidate()], WrongSymbolAdapter(), now=NOW,
        intervals=("1d",), bars_limit=5,
    )
    item = result["results"][0]
    assert item["status"] == "failed"
    assert "1d" in item["errors"]
    assert "returned symbol" in item["errors"]["1d"]


def test_invalid_interval_rejected_before_provider_call():
    with pytest.raises(ValueError, match="supported intervals"):
        import asyncio
        asyncio.run(run_autonomous_research(
            [candidate()], SyntheticFixtureAdapter(), now=NOW,
            intervals=("weekly",),
        ))
