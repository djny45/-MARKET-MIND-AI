"""Tests for extended flow analytics and existing-agent research routing."""
import unittest

from app import trade_flow
from app.intelligence_research import (
    build_research_finding, manifest, resolve_skill, supported_topics,
)


def trade(event_id, side, qty, price, when="2026-11-26T12:00:00Z"):
    return {
        "event_id": event_id, "event_time": when, "event_type": "trade",
        "instrument_id": "crypto:okx:BTC-USDT", "provider": "okx-public",
        "venue": "OKX", "payload": {"side": side, "quantity": qty, "price": price},
    }


class FlowSummaryTests(unittest.TestCase):
    def test_notional_and_relative_size(self):
        summary = trade_flow.build_market_flow_summary([
            trade("t1", "buy", 1, 100),
            trade("t2", "sell", 2, 50),
            trade("t3", "buy", 3, 200),
        ])
        self.assertEqual(summary["buy_notional"], 700.0)
        self.assertEqual(summary["sell_notional"], 100.0)
        self.assertEqual(summary["flow_direction"], "buy_dominant")
        self.assertEqual(summary["buy_share"], 0.875)
        self.assertEqual(summary["trades"][2]["relative_size"], 1.0)

    def test_unpriced_trades_are_excluded_not_imputed(self):
        summary = trade_flow.build_market_flow_summary([
            trade("t1", "buy", 1, None),
            trade("t2", "sell", 1, 100),
        ])
        self.assertEqual(summary["unpriced_trades_excluded"], 1)
        self.assertEqual(summary["buy_notional"], 0.0)
        self.assertEqual(summary["flow_direction"], "sell_dominant")

    def test_large_trade_threshold(self):
        summary = trade_flow.build_market_flow_summary([
            trade("t1", "buy", 1, 100),
            trade("t2", "sell", 10, 1000),
        ], large_trade_notional=500)
        self.assertEqual(len(summary["large_trades"]), 1)
        self.assertEqual(summary["large_trades"][0]["event_id"], "t2")

    def test_invalid_threshold_rejected(self):
        with self.assertRaises(ValueError):
            trade_flow.build_market_flow_summary([], large_trade_notional=-1)

    def test_visual_dots_encode_side_and_relative_notional(self):
        dots = trade_flow.build_visual_trade_dots([
            trade("t1", "buy", 1, 100),
            trade("t2", "sell", 2, 100),
        ])
        self.assertEqual(dots["count"], 2)
        buy = next(d for d in dots["dots"] if d["side"] == "buy")
        sell = next(d for d in dots["dots"] if d["side"] == "sell")
        self.assertEqual(buy["colour"], "#62b58e")
        self.assertEqual(sell["colour"], "#d77970")
        self.assertEqual(sell["size"], 1.0)
        self.assertEqual(buy["size"], 0.5)

    def test_liquidation_summary(self):
        events = [{
            "event_id": "l1", "event_type": "liquidation",
            "event_time": "2026-11-26T12:00:00Z",
            "provider": "okx-public", "venue": "OKX",
            "payload": {"side": "long", "price": 60000, "quantity": 2},
        }]
        row = trade_flow.build_liquidation_summary(events)
        self.assertEqual(row["liquidation_events"], 1)
        self.assertEqual(row["long_notional"], 120000.0)
        self.assertEqual(row["events"][0]["venue"], "OKX")

    def test_existing_bucket_contract_unchanged(self):
        buckets = trade_flow.build_trade_flow_buckets([
            trade("t1", "buy", 1, 100), trade("t2", "sell", 1, 100),
        ])
        self.assertTrue(buckets["cvd_available"])
        self.assertEqual(buckets["buckets"][0]["buy_volume"], 1.0)


class AgentRoutingTests(unittest.TestCase):
    def test_topics_map_to_allowlisted_existing_skills(self):
        for topic in supported_topics():
            row = resolve_skill(topic)
            self.assertTrue(row["available"], topic)
            self.assertTrue(row["skill_id"].startswith("mm-skill-"))
            self.assertFalse(row["new_agents_created"])
            self.assertFalse(row["new_skills_created"])

    def test_unknown_topic_rejected(self):
        with self.assertRaises(ValueError):
            resolve_skill("unsupported")

    def test_manifest_declares_no_duplicate_ecosystem(self):
        result = manifest()
        self.assertFalse(result["new_agents_created"])
        self.assertFalse(result["new_skills_created"])
        self.assertFalse(result["new_memory_system_created"])
        self.assertFalse(result["credential_isolation"]["broker_credentials_sent_to_agents"])

    def test_finding_separates_fact_calculation_and_interpretation(self):
        finding = build_research_finding(
            topic="crypto_order_flow", instrument="BTCUSDT", market="crypto",
            source="okx-public", event_timestamp="2026-11-26T12:00:00Z",
            retrieval_timestamp="2026-11-26T12:00:05Z",
            observed_facts=["Funding rate is 0.0001"],
            calculated_indicators={"imbalance": 0.2},
            interpretation="Buy pressure may persist",
            confidence="low",
            limitations=["Public REST snapshot only"],
        )
        content = finding["content_json"]
        self.assertEqual(content["provenance"]["source"], "okx-public")
        self.assertEqual(content["observed_facts"], ["Funding rate is 0.0001"])
        self.assertEqual(content["calculated_indicators"]["imbalance"], 0.2)
        self.assertIn("hypothesis", content["interpretation_label"])
        self.assertFalse(content["data_boundary"]["broker_credentials_seen"])

    def test_missing_provenance_stays_visible(self):
        finding = build_research_finding(
            topic="gold_activity", instrument="PAXG", market="crypto",
            source="coingecko-gold-token", event_timestamp=None,
            retrieval_timestamp=None, observed_facts=["Price is 3559.46"],
        )
        self.assertIsNone(finding["content_json"]["provenance"]["event_timestamp"])

    def test_skill_bridge_submits_to_existing_task_system(self):
        import os
        import tempfile

        os.environ["MARKET_MIND_DB"] = tempfile.mkdtemp() + "/bridge.db"
        from app.intelligence_research import submit_market_structure_research

        result = submit_market_structure_research(
            agent_id="worker_001", instrument="BTCUSDT", market="crypto",
            source="okx-public", event_timestamp="2026-11-26T12:00:00Z",
            retrieval_timestamp="2026-11-26T12:00:05Z",
            observed_facts=["Funding rate is 0.0001"],
        )
        self.assertTrue(result["task_id"])
        self.assertEqual(result["skill_id"], "tredye-market-structure-research")
        self.assertIn("observed_facts", result["finding"])
        self.assertFalse(result["finding"]["data_boundary"]["broker_execution"])


if __name__ == "__main__":
    unittest.main()
