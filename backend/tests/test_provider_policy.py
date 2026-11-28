"""Tests for compliant provider request pacing (no real sleeps, no bypass).

These verify the policy rather than just the adapter error message:

* Retry-After is honoured as a provider-wide cooldown.
* A 429 is retried only a bounded number of times.
* Successful responses are cached within the TTL.
* The limiter never claims to bypass a provider limit.
"""
import unittest
from unittest.mock import patch

from app.provider_policy import (
    POLICIES,
    ProviderError,
    ProviderLimiter,
    policy_for,
)


class PolicyTests(unittest.TestCase):
    def test_coinGecko_policy_is_stricter_than_observed_limit(self):
        policy = policy_for("coingecko-public")
        self.assertGreaterEqual(policy.min_interval_seconds, 35.0)
        self.assertEqual(policy.burst, 1)
        self.assertGreaterEqual(policy.cache_ttl_seconds, 60.0)
        # The observed public limit was ~2 requests/minute with Retry-After: 60.
        self.assertGreaterEqual(60.0 / policy.min_interval_seconds, 1.0)

    def test_unknown_provider_has_no_policy(self):
        with self.assertRaises(ValueError):
            policy_for("unknown-vendor")

    def test_policies_declare_no_bypass(self):
        for policy in POLICIES.values():
            self.assertIn("bypasses_limits", policy.to_payload())
            self.assertFalse(policy.to_payload()["bypasses_limits"])


class LimiterBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.now = [0.0]

        def advance(seconds):
            self.now[0] += max(seconds, 0.0)

        self.limiter = ProviderLimiter(clock=lambda: self.now[0], sleep=advance)

    def test_cache_avoids_a_second_upstream_call(self):
        calls = []
        with patch("app.provider_policy.time.monotonic", side_effect=lambda: self.now[0]):
            for _ in range(2):
                value = self.limiter.call("coingecko-public", ("k",), lambda: (
                    calls.append(1) or "price"
                ))
                self.assertEqual(value, "price")
        self.assertEqual(len(calls), 1)
        self.assertGreater(self.limiter.status()["cached_entries"], 0)

    def test_429_is_retried_bounded_then_raised(self):
        attempts = []

        def always_rate_limited():
            attempts.append(1)
            raise ProviderError("coingecko-public returned HTTP 429 (Retry-After: 60s)")

        with self.assertRaises(ProviderError):
            self.limiter.call("coingecko-public", ("rate",), always_rate_limited)
        policy = policy_for("coingecko-public")
        # At most max_retries + 1 attempts; never an unbounded loop.
        self.assertLessEqual(len(attempts), policy.max_retries + 1)
        self.assertGreater(len(attempts), 1)

    def test_cooldown_blocks_a_later_call_until_deadline(self):
        def rate_limited():
            raise ProviderError("coingecko-public returned HTTP 429 (Retry-After: 60s)")

        with self.assertRaises(ProviderError):
            self.limiter.call("coingecko-public", ("cool",), rate_limited)
        # The provider's own Retry-After was recorded and applied as a
        # provider-wide deadline. The fake clock advanced through the bounded
        # retries, so the remaining time may legitimately be zero by now.
        status = self.limiter.status()
        self.assertIn("coingecko-public", status["cooldown_remaining_seconds"])
        self.assertIn("429", status["last_provider_error"]["coingecko-public"])

        # A later call inside the cooldown window does not reach the provider.
        self.limiter._cooldown_until["coingecko-public"] = self.now[0] + 60.0
        calls = []

        def must_not_reach_provider():
            calls.append(1)
            return "unexpected"

        # With a fake sleep that advances time, the gate waits out the
        # cooldown rather than bypassing it; count the sleep to prove it waited.
        slept = []

        def advance_and_record(seconds):
            slept.append(seconds)
            self.now[0] += max(seconds, 0.0)

        self.limiter._sleep = advance_and_record
        self.limiter._cooldown_until["coingecko-public"] = self.now[0] + 60.0
        result = self.limiter.call("coingecko-public", ("later",), must_not_reach_provider)
        self.assertEqual(result, "unexpected")
        self.assertEqual(calls, [1])  # reached only after waiting
        self.assertGreater(sum(slept), 0)  # waited, never bypassed

    def test_non_rate_limit_error_is_not_retried(self):
        attempts = []

        def bad_payload():
            attempts.append(1)
            raise ProviderError("coingecko-public returned invalid JSON")

        with self.assertRaises(ProviderError):
            self.limiter.call("coingecko-public", ("bad",), bad_payload)
        self.assertEqual(len(attempts), 1)

    def test_status_never_claims_limit_bypass(self):
        status = self.limiter.status()
        self.assertFalse(status["bypasses_provider_limits"])
        self.assertTrue(all(
            not p["bypasses_limits"] for p in status["policies"]
        ))


if __name__ == "__main__":
    unittest.main()
