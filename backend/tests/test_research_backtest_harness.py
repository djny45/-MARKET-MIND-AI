import unittest

from app.research_backtest_harness import (
    BacktestConfig,
    Hypothesis,
    HypothesisRegistry,
    benjamini_hochberg,
    evaluate_candidates,
    generate_synthetic_bars,
    mean_reversion_signal,
    momentum_signal,
    run_backtest,
    split_bars,
)


class BacktestHarnessTests(unittest.TestCase):
    def setUp(self):
        self.bars = generate_synthetic_bars(300, seed=42)
        self.config = BacktestConfig(seed=42)

    def test_synthetic_data_is_deterministic(self):
        self.assertEqual(self.bars, generate_synthetic_bars(300, seed=42))
        self.assertNotEqual(self.bars, generate_synthetic_bars(300, seed=43))

    def test_split_is_chronological_and_disjoint(self):
        splits = split_bars(self.bars, self.config)
        train, validation, test = splits["train"], splits["validation"], splits["test"]
        self.assertEqual(len(train) + len(validation) + len(test), len(self.bars))
        self.assertLess(train[-1].timestamp, validation[0].timestamp)
        self.assertLess(validation[-1].timestamp, test[0].timestamp)

    def test_backtest_is_reproducible_and_shadow_only(self):
        first = run_backtest(self.bars, momentum_signal(10), self.config)
        second = run_backtest(self.bars, momentum_signal(10), self.config)
        self.assertEqual(first["manifest"], second["manifest"])
        self.assertEqual(first["equity_curve"], second["equity_curve"])
        self.assertTrue(all(order["executed"] is False for order in first["shadow_orders"]))
        self.assertTrue(all(order["mode"] == "shadow_log_only" for order in first["shadow_orders"]))
        self.assertFalse(first["broker_execution"])
        self.assertTrue(first["research_only"])

    def test_costs_reduce_returns(self):
        free = run_backtest(self.bars, momentum_signal(10), BacktestConfig(seed=42, fee_bps=0, slippage_bps=0))
        costly = run_backtest(self.bars, momentum_signal(10), BacktestConfig(seed=42, fee_bps=50, slippage_bps=50))
        self.assertLess(costly["final_equity"], free["final_equity"])

    def test_flat_strategy_has_no_orders(self):
        result = run_backtest(self.bars, lambda history: 0, self.config)
        self.assertEqual(result["trade_count"], 0)
        self.assertEqual(result["total_return"], 0.0)

    def test_bh_correction(self):
        adjusted = benjamini_hochberg([0.01, 0.02, 0.5])
        self.assertEqual(len(adjusted), 3)
        self.assertLessEqual(adjusted[0], adjusted[1])
        self.assertLessEqual(adjusted[1], adjusted[2])
        self.assertLessEqual(adjusted[-1], 1.0)
        self.assertEqual(benjamini_hochberg([]), [])

    def test_candidate_evaluation_reports_corrected_significance(self):
        result = evaluate_candidates(
            self.bars,
            {"momentum": momentum_signal(10), "mean_reversion": mean_reversion_signal(10)},
            self.config,
        )
        self.assertEqual(result["correction"], "benjamini_hochberg")
        self.assertEqual(len(result["candidates"]), 2)
        for candidate in result["candidates"]:
            self.assertGreaterEqual(candidate["q_value"], candidate["p_value"] - 1e-9)
            if candidate["promote"]:
                self.assertLess(candidate["q_value"], 0.05)
                self.assertGreater(candidate["test_sharpe"], 0)

    def test_hypothesis_registry_is_append_only(self):
        registry = HypothesisRegistry()
        registry.register(Hypothesis("h1", "momentum beats baseline", {"lookback": 10}, created_at="2026-01-01"))
        with self.assertRaises(ValueError):
            registry.register(Hypothesis("h1", "duplicate"))
        registry.update("h1", "tested")
        self.assertEqual(registry.list()[0]["status"], "tested")

    def test_invalid_config_is_rejected(self):
        with self.assertRaises(ValueError):
            BacktestConfig(train_fraction=0.95).validate()
        with self.assertRaises(ValueError):
            BacktestConfig(fee_bps=-1).validate()


if __name__ == "__main__":
    unittest.main()
