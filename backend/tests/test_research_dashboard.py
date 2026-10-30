import unittest

from app.research_dashboard import build_research_dashboard


class ResearchDashboardTests(unittest.TestCase):
    def test_summarizes_timeframes_quality_clusters_and_breadth(self):
        report = {
            "symbol": "BTCUSD",
            "timeframes": {
                "1h": {
                    "data_quality": {"quality_status": "no_structural_issues_detected", "bars_checked": 60},
                    "chart_research": {
                        "mode": "descriptive_research_only",
                        "latest_bar_timestamp": "2026-01-01T00:00:00+00:00",
                        "latest_close": 100,
                        "indicators": {"rsi14": 55.2, "atr14": 2.1},
                        "observed_structure": {"moving_average_regime": "mixed_or_sideways_average_structure"},
                        "warnings": [],
                    },
                    "historical_price_clusters": {"clusters": {
                        "historical_swing_high": [{"touch_count": 2}],
                        "historical_swing_low": [],
                    }},
                },
                "4h": {
                    "data_quality": {"quality_status": "issues_detected", "bars_checked": 4},
                    "chart_research": None,
                    "historical_price_clusters": None,
                },
            },
            "coverage": {"timeframes_with_insufficient_bars": ["4h"]},
            "cross_timeframe": {"status": "calculated"},
            "cross_asset_correlation": None,
            "market_breadth": {"latest_observation": {
                "timestamp": "2026-01-01T00:00:00+00:00",
                "advancing": 3, "declining": 1, "unchanged": 0,
            }},
        }
        result = build_research_dashboard(report)
        self.assertEqual(result["symbol"], "BTCUSD")
        self.assertEqual(result["data_quality"]["timeframes_with_issues"], 1)
        self.assertEqual(result["historical_price_clusters"]["confirmed_swing_high_cluster_count"], 1)
        self.assertEqual(result["timeframes"][1]["status"], "unavailable_or_insufficient")
        self.assertEqual(result["market_breadth_latest"]["advancing"], 3)
        self.assertEqual(result["execution"], "disabled")

    def test_missing_optional_sections_stay_unavailable(self):
        result = build_research_dashboard({
            "symbol": "ETHUSD", "timeframes": {},
            "coverage": {"timeframes_with_insufficient_bars": []},
            "cross_timeframe": None, "cross_asset_correlation": None,
            "market_breadth": None,
        })
        self.assertIsNone(result["market_breadth_latest"])
        self.assertIsNone(result["cross_asset_correlation"])
        self.assertEqual(result["timeframes"], [])


if __name__ == "__main__":
    unittest.main()
