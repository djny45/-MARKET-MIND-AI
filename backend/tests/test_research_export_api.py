import json
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.main import export_research_evidence


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
        get_bars.assert_called_once_with("btcusd", "1h", 250)

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
