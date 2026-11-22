import unittest

from app.research_regime import Regime, detect_regime, drift_report


class RegimeDetectionTests(unittest.TestCase):
    def test_trend_up_regime(self):
        returns = [0.001] * 50
        regime = detect_regime(returns)
        self.assertEqual(regime.label, "TREND_UP")

    def test_trend_down_regime(self):
        returns = [-0.001] * 50
        regime = detect_regime(returns)
        self.assertEqual(regime.label, "TREND_DOWN")

    def test_low_volatility_regime(self):
        returns = [0.0002] * 50
        regime = detect_regime(returns)
        self.assertEqual(regime.label, "LOW_VOL")

    def test_high_volatility_regime(self):
        returns = [0.008, -0.008] * 25
        regime = detect_regime(returns, window=20)
        self.assertEqual(regime.label, "HIGH_VOL")

    def test_mixed_regime_for_random_like_returns(self):
        returns = [0.0] * 50
        regime = detect_regime(returns)
        self.assertIn(regime.label, {"LOW_VOL", "MIXED"})

    def test_requires_enough_returns(self):
        with self.assertRaises(ValueError):
            detect_regime([0.0] * 5)
        with self.assertRaises(ValueError):
            detect_regime([0.0] * 19, window=20)


class DriftReportTests(unittest.TestCase):
    def test_stable_regime_reports_no_drift(self):
        returns = [0.001] * 100
        report = drift_report(returns)
        self.assertEqual(report["baseline"]["label"], "TREND_UP")
        self.assertEqual(report["current"]["label"], "TREND_UP")
        self.assertFalse(report["signal_drift"])

    def test_regime_change_is_a_signal(self):
        returns = [0.0004] * 50 + [-0.0008] * 50
        report = drift_report(returns)
        self.assertTrue(report["label_changed"] or report["signal_drift"])

    def test_report_is_reproducible(self):
        returns = [0.001, -0.001, 0.002, -0.002] * 25
        self.assertEqual(drift_report(returns), drift_report(returns))

    def test_requires_sufficient_history(self):
        with self.assertRaises(ValueError):
            drift_report([0.001] * 10)


if __name__ == "__main__":
    unittest.main()
