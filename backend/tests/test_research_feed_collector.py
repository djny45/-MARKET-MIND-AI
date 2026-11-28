import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
SCRIPT = BACKEND.parent / "scripts" / "ingest_crypto_silver_oil_research.py"
SPEC = importlib.util.spec_from_file_location("research_feed_collector", SCRIPT)
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


class ResearchFeedCollectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_platform_symbol_is_used_for_storage_and_historical_status_is_preserved(self):
        batch = SimpleNamespace(
            symbol="BTC-USD",
            interval="15m",
            status=SimpleNamespace(value="historical"),
            source="yahoo-finance-chart",
            bars=[object()],
            model_copy=lambda update: SimpleNamespace(
                symbol=update["symbol"],
                interval="15m",
                status=SimpleNamespace(value="historical"),
                source="yahoo-finance-chart",
                bars=[object()],
            ),
        )
        adapter = SimpleNamespace(get_bars=AsyncMock(return_value=batch))
        with patch.object(collector, "store_batch", return_value={"stored": 1}) as store:
            result = await collector.ingest_once(adapter)
        stored_batch = store.call_args.args[0]
        self.assertEqual(stored_batch.symbol, "BTCUSD")
        self.assertEqual(stored_batch.source, "yahoo-finance-chart")
        self.assertEqual(stored_batch.status.value, "historical")
        self.assertEqual(result["BTCUSD"]["stored"], 1)

    async def test_provider_failure_is_isolated_per_symbol(self):
        adapter = SimpleNamespace(get_bars=AsyncMock(side_effect=[
            RuntimeError("provider unavailable"),
            RuntimeError("provider unavailable"),
            RuntimeError("provider unavailable"),
            RuntimeError("provider unavailable"),
            RuntimeError("provider unavailable"),
        ]))
        with patch.object(collector, "store_batch") as store:
            result = await collector.ingest_once(adapter)
        self.assertEqual(set(result), set(collector.SYMBOLS))
        self.assertTrue(all(item["status"] == "unavailable" for item in result.values()))
        store.assert_not_called()


if __name__ == "__main__":
    unittest.main()
