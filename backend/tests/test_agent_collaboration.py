import unittest

from app.agent_collaboration import build_collaboration_brief


class AgentCollaborationBriefTests(unittest.TestCase):
    def message(self, market, value, quality="partial", topic="macro"):
        return {
            "agent_id": f"{market}-research",
            "market_group": market,
            "topic": topic,
            "quality_status": quality,
            "payload": {
                "finding_key": "monthly_inflation",
                "finding_value": value,
                "unit": "percent",
            },
        }

    def test_roundtable_compares_findings_across_all_four_markets(self):
        messages = [
            self.message("india", 4.2, "verified_by_importer"),
            self.message("us", 3.1, "partial"),
            self.message("crypto", 4.2, "unverified"),
            self.message("forex", 4.2, "synthetic"),
        ]
        brief = build_collaboration_brief(messages)
        self.assertEqual(brief["messages_reviewed"], 4)
        self.assertEqual(set(brief["participating_market_groups"]), {"india", "us", "crypto", "forex"})
        self.assertTrue(brief["cross_market_context_available"])
        comparison = brief["finding_comparisons"][0]
        self.assertEqual(comparison["matching_value_groups"], 2)
        self.assertTrue(comparison["cross_market_comparable"])
        self.assertEqual(brief["quality_label_counts"]["synthetic"], 1)

    def test_single_market_is_not_cross_market_context(self):
        brief = build_collaboration_brief([self.message("india", 4.2)])
        self.assertFalse(brief["cross_market_context_available"])
        self.assertEqual(brief["market_message_counts"]["india"], 1)

    def test_non_comparable_payload_is_not_promoted_to_finding(self):
        message = self.message("us", 3.1)
        message["payload"]["finding_value"] = {"estimate": 3.1}
        brief = build_collaboration_brief([message])
        self.assertEqual(brief["finding_comparisons"], [])

    def test_invalid_input_rejected(self):
        with self.assertRaises(ValueError):
            build_collaboration_brief({})


if __name__ == "__main__":
    unittest.main()
