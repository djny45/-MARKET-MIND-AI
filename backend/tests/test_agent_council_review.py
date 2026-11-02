import unittest

from app.agent_council_review import review_council_outputs


class AgentCouncilReviewTests(unittest.TestCase):
    def test_normalized_identical_summaries_are_fingerprinted(self):
        result = review_council_outputs({"members": [
            {"agent_id": "agent_a", "status": "completed", "analysis": "  MARKET   rises "},
            {"agent_id": "agent_b", "status": "completed", "analysis": "market rises"},
            {"agent_id": "agent_c", "status": "unavailable", "analysis": None},
        ]})
        self.assertEqual(result["member_count_with_analysis"], 2)
        self.assertEqual(result["unique_analysis_fingerprints"], 1)
        self.assertEqual(result["identical_output_groups"][0]["member_count"], 2)
        self.assertIsNone(result["consensus"])
        self.assertFalse(result["paper_trading"])

    def test_distinct_summaries_are_not_called_disagreement(self):
        result = review_council_outputs({"members": [
            {"agent_id": "agent_a", "analysis": "Evidence A"},
            {"agent_id": "agent_b", "analysis": "Evidence B"},
        ]})
        self.assertEqual(result["unique_analysis_fingerprints"], 2)
        self.assertEqual(result["identical_output_groups"], [])
        self.assertIn("not inferred", result["interpretation"])

    def test_rejects_malformed_or_oversized_member_list(self):
        with self.assertRaises(ValueError):
            review_council_outputs([])
        with self.assertRaises(ValueError):
            review_council_outputs({"members": [{}]})
        with self.assertRaises(ValueError):
            review_council_outputs({"members": [{"agent_id": "a", "analysis": 3}]})
        with self.assertRaises(ValueError):
            review_council_outputs({"members": [{}] * 9})


if __name__ == "__main__":
    unittest.main()
