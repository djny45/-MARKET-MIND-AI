import unittest

from app.env_validation import validate_environment


class EnvironmentValidationTests(unittest.TestCase):
    def test_safe_defaults_are_valid(self):
        result = validate_environment({})
        self.assertTrue(result["ok"])
        self.assertEqual(result["issues"], [])
        self.assertFalse(result["secret_values_exposed"])

    def test_auth_requires_a_long_token(self):
        result = validate_environment({"API_AUTH_REQUIRED": "true", "API_AUTH_TOKEN": "short"})
        self.assertFalse(result["ok"])
        self.assertTrue(any("API_AUTH_TOKEN" in issue for issue in result["issues"]))
        good = validate_environment({"API_AUTH_REQUIRED": "true", "API_AUTH_TOKEN": "s" * 48})
        self.assertTrue(good["ok"])
        self.assertTrue(good["checks"]["auth_token_configured"])

    def test_cors_origins_are_validated(self):
        wildcard = validate_environment({"FRONTEND_ORIGINS": "*"})
        self.assertFalse(wildcard["ok"])
        self.assertTrue(any("wildcard" in issue for issue in wildcard["issues"]))
        invalid = validate_environment({"FRONTEND_ORIGINS": "not-a-url"})
        self.assertFalse(invalid["ok"])

    def test_numeric_settings_are_validated(self):
        self.assertFalse(validate_environment({"API_RATE_LIMIT_PER_MINUTE": "abc"})["ok"])
        self.assertFalse(validate_environment({"API_RATE_LIMIT_PER_MINUTE": "-1"})["ok"])
        self.assertFalse(validate_environment({"MARKET_MIND_STARTUP_RECOVERY": "maybe"})["ok"])

    def test_secret_values_never_appear_in_output(self):
        token = "s" * 48
        result = validate_environment({"API_AUTH_REQUIRED": "true", "API_AUTH_TOKEN": token})
        self.assertNotIn(token, str(result))


if __name__ == "__main__":
    unittest.main()
