import unittest

from app.setup_report import build_setup_report


class SetupReportTests(unittest.TestCase):
    def test_long_risk_reward(self):
        report = build_setup_report("btcusd", "long", 100, 95, 110)
        self.assertEqual(report["symbol"], "BTCUSD")
        self.assertEqual(report["risk_reward_ratio"], 2.0)
        self.assertEqual(report["execution"], "disabled")

    def test_short_risk_reward(self):
        report = build_setup_report("ETHUSD", "short", 100, 105, 90)
        self.assertEqual(report["risk_distance"], 5)
        self.assertEqual(report["reward_distance"], 10)
        self.assertEqual(report["risk_reward_ratio"], 2.0)

    def test_rejects_invalid_level_order(self):
        with self.assertRaises(ValueError):
            build_setup_report("BTCUSD", "long", 100, 105, 110)

    def test_rejects_zero_price(self):
        with self.assertRaises(ValueError):
            build_setup_report("BTCUSD", "long", 100, 0, 110)


if __name__ == "__main__":
    unittest.main()
