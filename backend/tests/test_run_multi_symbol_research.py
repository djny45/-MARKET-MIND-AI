"""Tests for multi-symbol historical research batch runner (mocked data)."""
import unittest
from unittest.mock import patch

from run_multi_symbol_research import run_batch


class MultiSymbolResearchTests(unittest.IsolatedAsyncioTestCase):
    async def test_symbols_run_independently_and_failures_are_explicit(self):
        async def fake_run(symbol, bars, **kwargs):
            if symbol == "BAD":
                raise ValueError("mock provider failure")
            return {
                "evaluation_mode": "expanding_walk_forward",
                "data": {"dataset_sha256": f"hash-{symbol}"},
                "aggregate_mean_window_metrics": {"model": {"mae_log_return": 0.1}},
            }

        with patch("run_multi_symbol_research.run", side_effect=fake_run) as mocked:
            report = await run_batch(
                ["AAA", "BAD", "aaa", "BBB"], 500,
                walk_forward=True, min_train_samples=100, test_window_size=20,
            )

        self.assertEqual(report["requested_symbols"], ["AAA", "BAD", "BBB"])
        self.assertEqual(report["summary"], {
            "symbols_requested": 3, "symbols_succeeded": 2, "symbols_failed": 1,
        })
        self.assertEqual([x["status"] for x in report["results"]],
                         ["success", "error", "success"])
        self.assertEqual(report["results"][0]["dataset_sha256"], "hash-AAA")
        self.assertEqual(report["results"][1]["error_type"], "ValueError")
        self.assertNotIn("report", report["results"][1])
        self.assertEqual(mocked.call_count, 3)
        self.assertTrue(report["research_only"])

    async def test_empty_symbols_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            await run_batch([" ", ""], 500)


if __name__ == "__main__":
    unittest.main()
