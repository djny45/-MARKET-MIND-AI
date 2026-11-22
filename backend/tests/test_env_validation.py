import unittest

from app.env_validation import (
    EnvironmentValidationError,
    cookie_settings,
    enforce_environment,
    is_strict,
    trusted_proxy_settings,
    validate_environment,
)


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

    def test_strict_mode_is_advisory_by_default(self):
        self.assertFalse(is_strict({}))
        self.assertFalse(is_strict({"APP_ENV": "development"}))
        self.assertTrue(is_strict({"ENV_VALIDATION_STRICT": "1"}))
        self.assertTrue(is_strict({"APP_ENV": "production"}))
        self.assertEqual(enforce_environment({})["issues"], [])

    def test_strict_mode_fails_closed_on_weak_auth(self):
        env = {"APP_ENV": "production", "API_AUTH_TOKEN": "short"}
        result = validate_environment(env)
        self.assertFalse(result["ok"])
        self.assertTrue(result["strict_mode"])
        self.assertTrue(any("API_AUTH_TOKEN" in issue for issue in result["issues"]))
        with self.assertRaises(EnvironmentValidationError) as error:
            enforce_environment(env)
        self.assertTrue(any("API_AUTH_TOKEN" in issue for issue in error.exception.issues))
        self.assertNotIn("short", str(error.exception))

    def test_strict_mode_fails_closed_on_wildcard_and_insecure_cookies(self):
        env = {
            "ENV_VALIDATION_STRICT": "1",
            "API_AUTH_REQUIRED": "true",
            "API_AUTH_TOKEN": "s" * 48,
            "FRONTEND_ORIGINS": "https://example.com,*",
            "MARKET_MIND_COOKIE_SAMESITE": "none",
        }
        issues = validate_environment(env)["issues"]
        self.assertTrue(any("wildcard" in issue for issue in issues))
        self.assertTrue(any("SECURE_COOKIES" in issue for issue in issues))
        self.assertTrue(any("SAMESITE" in issue for issue in issues))
        with self.assertRaises(EnvironmentValidationError):
            enforce_environment(env)

    def test_strict_mode_accepts_fully_secured_configuration(self):
        env = {
            "ENV_VALIDATION_STRICT": "1",
            "API_AUTH_REQUIRED": "true",
            "API_AUTH_TOKEN": "s" * 48,
            "FRONTEND_ORIGINS": "https://example.com",
            "MARKET_MIND_SECURE_COOKIES": "true",
            "MARKET_MIND_COOKIE_SAMESITE": "strict",
        }
        result = enforce_environment(env)
        self.assertTrue(result["ok"])
        self.assertTrue(result["secret_values_exposed"] is False)

    def test_cookie_and_proxy_helpers_are_safely_configurable(self):
        self.assertEqual(cookie_settings({}), {"httponly": True, "samesite": "strict", "secure": False})
        self.assertEqual(
            cookie_settings({"MARKET_MIND_COOKIE_SAMESITE": "none", "MARKET_MIND_SECURE_COOKIES": "true"}),
            {"httponly": True, "samesite": "none", "secure": True},
        )
        self.assertEqual(trusted_proxy_settings({}), {"count": 0, "header": "x-forwarded-for"})
        self.assertEqual(
            trusted_proxy_settings({"MARKET_MIND_TRUSTED_PROXY_COUNT": "2"}),
            {"count": 2, "header": "x-forwarded-for"},
        )


if __name__ == "__main__":
    unittest.main()
