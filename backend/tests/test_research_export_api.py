import json
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.main import export_research_evidence, compare_export_bundles


class ResearchEvidenceExportApiTests(unittest.TestCase):
    def test_export_returns_downloadable_json_with_provenance(self):
        history = {
            "symbol": "BTCUSD", "interval": "1h", "source": "local-csv",
            "sources": ["local-csv"], "status": "historical",
            "retrieved_at": "2026-01-02T00:00:00Z",
            "first_timestamp": "2026-01-01T00:00:00Z",
            "last_timestamp": "2026-01-01T00:00:00Z",
            "bars": [{
                "timestamp": "2026-01-01T00:00:00Z", "source": "local-csv",
                "status": "historical", "retrieved_at": "2026-01-02T00:00:00Z",
                "open": 100, "high": 105, "low": 99, "close": 103, "volume": 1200,
            }, {
                "timestamp": "2026-01-01T01:00:00Z", "source": "local-csv",
                "status": "historical", "retrieved_at": "2026-01-02T00:00:00Z",
                "open": 103, "high": 106, "low": 102, "close": 104, "volume": 1300,
            }],
        }
        with patch("app.main.market_store.get_bars", return_value=history) as get_bars:
            response = export_research_evidence("btcusd", "1h", 250)
        payload = json.loads(response.body)
        self.assertEqual(response.media_type, "application/json")
        self.assertIn('attachment; filename="BTCUSD-1h-research-evidence.json"',
                      response.headers["content-disposition"])
        self.assertEqual(payload["observations"], history["bars"])
        self.assertEqual(payload["scope"]["source"], "local-csv")
        self.assertEqual(payload["report_type"], "historical_research_evidence")
        self.assertEqual(payload["integrity"]["algorithm"], "sha256")
        get_bars.assert_called_once_with("btcusd", "1h", 250)

    def test_compare_endpoint_returns_observation_differences(self):
        before = {
            "report_type": "historical_research_evidence",
            "scope": {"symbol": "BTCUSD", "interval": "1h"},
            "observations": [{"timestamp": "2026-01-01T00:00:00Z", "source": "csv", "close": 10}],
        }
        after = {
            "report_type": "historical_research_evidence",
            "scope": {"symbol": "BTCUSD", "interval": "1h"},
            "observations": [{"timestamp": "2026-01-01T00:00:00Z", "source": "csv", "close": 11}],
        }
        result = compare_export_bundles({"before": before, "after": after})
        self.assertEqual(result["counts"]["changed"], 1)

    def test_compare_endpoint_rejects_scope_mismatch(self):
        before = {"report_type": "historical_research_evidence",
                  "scope": {"symbol": "BTCUSD", "interval": "1h"}, "observations": []}
        after = {"report_type": "historical_research_evidence",
                 "scope": {"symbol": "ETHUSD", "interval": "1h"}, "observations": []}
        with self.assertRaises(HTTPException) as error:
            compare_export_bundles({"before": before, "after": after})
        self.assertEqual(error.exception.status_code, 400)

    def test_export_supports_empty_history(self):
        with patch("app.main.market_store.get_bars", return_value={
            "symbol": "ETHUSD", "interval": "4h", "bars": [], "sources": []
        }):
            response = export_research_evidence("ETHUSD", "4h", 500)
        payload = json.loads(response.body)
        self.assertEqual(payload["observations"], [])
        self.assertEqual(payload["timeline"]["status"], "no_stored_observations")

    def test_export_rejects_unsupported_interval_and_limit(self):
        with self.assertRaises(HTTPException) as interval_error:
            export_research_evidence("BTCUSD", "5m", 500)
        self.assertEqual(interval_error.exception.status_code, 400)
        with self.assertRaises(HTTPException) as limit_error:
            export_research_evidence("BTCUSD", "1h", 5001)
        self.assertEqual(limit_error.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
