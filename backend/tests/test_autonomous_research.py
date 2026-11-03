from datetime import datetime, timezone
import unittest

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


class AutonomousResearchTests(unittest.IsolatedAsyncioTestCase):
    async def test_autonomous_loop_prioritizes_and_builds_descriptive_report(self):
        result = await run_autonomous_research(
            [candidate()], SyntheticFixtureAdapter(), now=NOW,
            intervals=("1d",), bars_limit=5,
        )
        self.assertEqual(result["mode"], "autonomous_descriptive_market_research")
        self.assertEqual(result["research_queue_size"], 1)
        item = result["results"][0]
        self.assertEqual(item["symbol"], "TEST")
        self.assertEqual(item["status"], "completed")
        report = item["timeframes"]["1d"]
        self.assertEqual(report["mode"], "descriptive_research_only")
        self.assertEqual(report["data_status"], "synthetic")
        self.assertEqual(report["execution"], "disabled")
        self.assertEqual(result["shared_ai_synthesis"]["status"], "not_requested")

    async def test_candidate_generator_is_consumed_once_and_counted(self):
        candidates = (item for item in [candidate("ONE"), candidate("TWO")])
        result = await run_autonomous_research(
            candidates, SyntheticFixtureAdapter(), now=NOW,
            intervals=("1d",), bars_limit=5,
        )
        self.assertEqual(result["candidates_received"], 2)
        self.assertEqual([item["symbol"] for item in result["results"]], ["ONE", "TWO"])

    async def test_invalid_adapter_symbol_isolated_as_timeframe_error(self):
        class WrongSymbolAdapter:
            name = "wrong-symbol"

            async def get_bars(self, symbol, interval, limit):
                return await SyntheticFixtureAdapter().get_bars("WRONG", interval, 5)

        result = await run_autonomous_research(
            [candidate()], WrongSymbolAdapter(), now=NOW,
            intervals=("1d",), bars_limit=5,
        )
        item = result["results"][0]
        self.assertEqual(item["status"], "failed")
        self.assertIn("1d", item["errors"])
        self.assertIn("returned symbol", item["errors"]["1d"])

    async def test_invalid_interval_rejected_before_provider_call(self):
        with self.assertRaisesRegex(ValueError, "supported intervals"):
            await run_autonomous_research(
                [candidate()], SyntheticFixtureAdapter(), now=NOW,
                intervals=("weekly",),
            )


if __name__ == "__main__":
    unittest.main()
