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


    def test_retrieval_freshness_uses_explicit_caller_threshold(self):
        payload = {
            "symbol": "BTCUSD", "interval": "1d", "status": "historical",
            "source": "provider-x", "retrieved_at": "2020-01-02T00:00:00Z",
            "bars": [],
        }
        report = validate_market_data_payload(payload, max_retrieval_age_seconds=60)
        self.assertTrue(report["valid"])
        self.assertEqual(report["retrieval_freshness"], "stale")
        self.assertEqual(report["freshness_threshold_seconds"], 60)
        self.assertTrue(any("caller-supplied age threshold" in item for item in report["warnings"]))

    def test_freshness_is_not_classified_without_explicit_threshold(self):
        report = validate_market_data_payload({
            "symbol": "BTCUSD", "interval": "1d", "status": "historical",
            "source": "provider-x", "retrieved_at": "2020-01-02T00:00:00Z",
            "bars": [],
        })
        self.assertIsNone(report["retrieval_freshness"])
        self.assertIsNone(report["freshness_threshold_seconds"])
        self.assertGreater(report["retrieval_age_seconds"], 0)

    def test_rejects_invalid_freshness_threshold(self):
        for value in (-1, True, float("inf"), "60"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "finite non-negative"):
                    validate_market_data_payload(
                        {"invalid": "payload"}, max_retrieval_age_seconds=value
                    )



    def test_future_retrieval_timestamp_is_flagged_not_called_fresh(self):
        report = validate_market_data_payload({
            "symbol": "BTCUSD", "interval": "1d", "status": "historical",
            "source": "provider-x", "retrieved_at": "2099-01-02T00:00:00Z",
            "bars": [],
        }, max_retrieval_age_seconds=60)
        self.assertTrue(report["valid"])
        self.assertEqual(report["retrieval_freshness"], "future_timestamp")
        self.assertLess(report["retrieval_age_seconds"], 0)
        self.assertTrue(any("in the future" in item for item in report["warnings"]))



    def test_market_data_validation_api_returns_freshness_report(self):
        from app.main import MarketDataValidationRequest, validate_market_data
        request = MarketDataValidationRequest(
            payload={
                "symbol": "BTCUSD", "interval": "1d", "status": "historical",
                "source": "provider-x", "retrieved_at": "2020-01-02T00:00:00Z",
                "bars": [],
            },
            max_retrieval_age_seconds=60,
        )
        report = validate_market_data(request)
        self.assertTrue(report["valid"])
        self.assertEqual(report["retrieval_freshness"], "stale")
        self.assertEqual(report["freshness_threshold_seconds"], 60)

    def test_market_data_validation_api_rejects_boolean_threshold(self):
        from pydantic import ValidationError
        from app.main import MarketDataValidationRequest
        with self.assertRaises(ValidationError):
            MarketDataValidationRequest(
                payload={"symbol": "BTCUSD"},
                max_retrieval_age_seconds=True,
            )

    def test_market_data_validation_api_bounds_threshold(self):
        from pydantic import ValidationError
        from app.main import MarketDataValidationRequest
        with self.assertRaises(ValidationError):
            MarketDataValidationRequest(
                payload={"symbol": "BTCUSD"},
                max_retrieval_age_seconds=31536001,
            )

if __name__ == "__main__":
    unittest.main()
