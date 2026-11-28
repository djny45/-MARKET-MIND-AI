import unittest

from app.model_access import (
    ModelAccessConfigurationError,
    model_assignment,
    model_tier_manifest,
)


class CloudModelTierTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "MARKET_MIND_MODEL_PROVIDER": "mercury",
            "MARKET_MIND_PREMIUM_MODEL": "premium-test-model",
            "MARKET_MIND_BASIC_MODEL": "basic-test-model",
            "INCEPTION_API_KEY": "test-secret",
            "INTELLIGENCE_CORE_ENABLED": "true",
        }

    def test_first_twenty_agents_receive_premium_tier(self):
        for index in range(1, 21):
            with self.subTest(index=index):
                result = model_assignment(f"worker_{index:03d}", self.env)
                self.assertEqual(result["tier"], "premium")
                self.assertEqual(result["model"], "premium-test-model")
                self.assertTrue(result["configured"])

    def test_remaining_five_hundred_thirty_agents_receive_standard_tier(self):
        for index in (21, 22, 275, 550):
            with self.subTest(index=index):
                result = model_assignment(f"worker_{index:03d}", self.env)
                self.assertEqual(result["tier"], "standard")
                self.assertEqual(result["model"], "basic-test-model")

    def test_unknown_agents_are_rejected(self):
        for agent_id in ("worker_000", "worker_551", "worker_x01", "", None):
            with self.subTest(agent_id=agent_id), self.assertRaises(ValueError):
                model_assignment(agent_id, self.env)

    def test_local_provider_is_rejected(self):
        env = {**self.env, "MARKET_MIND_MODEL_PROVIDER": "ollama"}
        with self.assertRaises(ModelAccessConfigurationError):
            model_assignment("worker_001", env)

    def test_missing_model_or_credential_is_not_ready(self):
        env = {**self.env}
        env.pop("MARKET_MIND_BASIC_MODEL")
        manifest = model_tier_manifest(env)
        self.assertFalse(manifest["ready"])
        self.assertFalse(manifest["inference_enabled"])

    def test_manifest_never_exposes_credentials(self):
        result = model_tier_manifest(self.env)
        self.assertNotIn("test-secret", repr(result))
        self.assertEqual(result["senior_agent_count"], 20)
        self.assertEqual(result["standard_agent_count"], 530)


if __name__ == "__main__":
    unittest.main()
