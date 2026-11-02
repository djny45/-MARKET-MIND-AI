import unittest

from app.market_data_validation import validate_market_data_payload


class MarketDataValidationReportTests(unittest.TestCase):
    def test_valid_payload_returns_summary_without_mutating_input(self):
        payload = {
            "symbol": " btcusd ",
            "interval": "1d",
            "status": "historical",
            "source": "provider-x",
            "retrieved_at": "2026-01-02T00:00:00Z",
            "bars": [{
                "timestamp": "2026-01-01T00:00:00Z",
                "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100,
            }],
        }
        original = repr(payload)
        report = validate_market_data_payload(payload)
        self.assertTrue(report["valid"])
        self.assertEqual(report["result"], "valid")
        self.assertEqual(report["error_count"], 0)
        self.assertEqual(report["schema_version"], 1)
        self.assertTrue(report["generated_at"].endswith("+00:00"))
        self.assertEqual(report["retrieved_at"], "2026-01-02T00:00:00+00:00")
        self.assertEqual(report["symbol"], "BTCUSD")
        self.assertEqual(report["bar_count"], 1)
        self.assertEqual(payload["symbol"], " btcusd ")
        self.assertEqual(repr(payload), original)
        self.assertEqual(report["errors"], [])

    def test_invalid_payload_returns_field_errors(self):
        report = validate_market_data_payload({
            "symbol": "BTCUSD",
            "interval": "1d",
            "status": "historical",
            "source": "provider-x",
            "retrieved_at": "2026-01-02T00:00:00Z",
            "bars": [{
                "timestamp": "2026-01-01T00:00:00Z",
                "open": 10, "high": 8, "low": 9, "close": 11, "volume": 100,
            }],
        })
        self.assertFalse(report["valid"])
        self.assertEqual(report["result"], "invalid")
        self.assertEqual(report["error_count"], len(report["errors"]))
        self.assertEqual(report["schema_version"], 1)
        self.assertTrue(report["generated_at"].endswith("+00:00"))
        self.assertTrue(report["errors"])
        self.assertIsNone(report["bar_count"])

    def test_empty_valid_batch_reports_null_timestamp_range(self):
        report = validate_market_data_payload({
            "symbol": "TEST",
            "interval": "1d",
            "status": "historical",
            "source": "provider-x",
            "retrieved_at": "2026-01-02T00:00:00Z",
            "bars": [],
        })
        self.assertTrue(report["valid"])
        self.assertIsNone(report["timestamp_start"])
        self.assertIsNone(report["timestamp_end"])


if __name__ == "__main__":
    unittest.main()
