import os
import tempfile
import unittest
from unittest.mock import patch

from app.agent_network import publish_message, read_messages, network_topology
from app.main import (AgentResearchMessageRequest, publish_agent_research_message,
                      agent_research_messages, agent_collaboration_brief)


class AgentNetworkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(self.temp.name, "agents.sqlite")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def message(self, agent, market, topic="macro", payload=None):
        return {
            "agent_id": agent, "market_group": market, "topic": topic,
            "source_refs": ["historical-import:batch-01"],
            "quality_status": "partial",
            "payload": payload or {"observation": "example", "window": "daily"},
        }

    def test_cross_market_agents_share_messages(self):
        publish_message(self.message("india-macro", "india"))
        publish_message(self.message("us-macro", "us"))
        result = read_messages(limit=20)
        self.assertEqual(result["count"], 2)
        self.assertTrue(result["cross_market_context"])
        self.assertEqual(set(result["peer_market_groups_in_sample"]), {"india", "us"})

    def test_market_filter_and_topic_filter(self):
        publish_message(self.message("crypto-vol", "crypto", "volatility"))
        publish_message(self.message("fx-macro", "forex", "macro"))
        result = read_messages(market_group="crypto", topic="volatility")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["messages"][0]["agent_id"], "crypto-vol")

    def test_invalid_market_and_payload_are_rejected(self):
        with self.assertRaises(ValueError):
            publish_message(self.message("bad", "global"))
        invalid = self.message("bad-payload", "india")
        invalid["payload"] = ["not", "an", "object"]
        with self.assertRaises(ValueError):
            publish_message(invalid)

    def test_network_topology_is_full_mesh(self):
        topology = network_topology()
        self.assertEqual(len(topology["connections"]), 12)
        self.assertEqual(topology["agent_runtime"], "analytical modules only; no LLM inference")

    def test_api_publish_and_read(self):
        request = AgentResearchMessageRequest(**self.message("api-india", "india"))
        published = publish_agent_research_message(request)
        result = agent_research_messages(None, "macro", 10)
        self.assertEqual(published["market_group"], "india")
        self.assertEqual(result["count"], 1)

    def test_api_cross_market_brief(self):
        publish_message(self.message("brief-india", "india", payload={
            "finding_key": "risk_context", "finding_value": "elevated", "unit": "label"
        }))
        publish_message(self.message("brief-us", "us", payload={
            "finding_key": "risk_context", "finding_value": "elevated", "unit": "label"
        }))
        brief = agent_collaboration_brief(None, 20)
        self.assertTrue(brief["cross_market_context_available"])
        self.assertEqual(brief["messages_reviewed"], 2)
        self.assertEqual(brief["finding_comparisons"][0]["matching_value_groups"], 1)


if __name__ == "__main__":
    unittest.main()
