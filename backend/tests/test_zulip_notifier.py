"""Tests for optional Zulip communication layer — no network, no duplicates."""
import os
import tempfile
import unittest
from unittest.mock import patch

import httpx

os.environ["MARKET_MIND_DB"] = tempfile.mkdtemp() + "/zulip.db"

from app import zulip_notifier as z
from app.market_data import DataStatus
from app.workers import list_workers


class ConfigTests(unittest.TestCase):
    def test_unconfigured_is_noop(self):
        with patch.dict(os.environ, {}, clear=True):
            state = z.config()
        self.assertFalse(state["configured"])
        self.assertFalse(state["enabled"])
        self.assertFalse(state["credentials_exposed"])
        self.assertFalse(state["inbound_commands_enabled"])

    def test_https_site_is_required_outside_loopback(self):
        with patch.dict(os.environ, {"ZULIP_SITE_URL": "http://example.com"}):
            state = z.config()
        self.assertIn("plaintext_site_url", state["issues"])

    def test_loopback_http_is_allowed_for_local_testing(self):
        with patch.dict(os.environ, {"ZULIP_SITE_URL": "http://127.0.0.1:9991"}):
            state = z.config()
        self.assertNotIn("plaintext_site_url", state["issues"])

    def test_streams_and_topics_are_fixed(self):
        manifest = z.STREAMS
        self.assertEqual(
            set(manifest),
            {"market-data", "agent-research", "system-operations",
             "ci-testing", "risk-governance"},
        )
        self.assertIn("US-stocks", manifest["market-data"])
        self.assertIn("GitHub-Actions", manifest["ci-testing"])

    def test_invalid_target_rejected(self):
        with self.assertRaises(ValueError):
            z.validate_target("unknown", "topic")
        with self.assertRaises(ValueError):
            z.validate_target("market-data", "GitHub-Actions")


class MessageTests(unittest.TestCase):
    def test_message_carries_provenance_and_status(self):
        row = z.build_message(
            stream="agent-research", topic="Research-results",
            message_type="task_completed", data_status="HISTORICAL",
            agent_id="worker_001", task_id="task-1", market="crypto",
            source="existing_task_store", content="Finding recorded",
        )
        self.assertEqual(row["agent_id"], "worker_001")
        self.assertEqual(row["task_id"], "task-1")
        self.assertEqual(row["data_status"], "HISTORICAL")
        self.assertTrue(row["dedupe_key"])
        self.assertIn("timestamp", row)

    def test_unknown_status_rejected(self):
        with self.assertRaises(ValueError):
            z.build_message(
                stream="market-data", topic="US-stocks",
                message_type="quote", data_status="UNVERIFIED",
                source="test", content="unverified",
            )

    def test_secret_is_redacted_before_payload(self):
        row = z.build_message(
            stream="ci-testing", topic="GitHub-Actions",
            message_type="ci", data_status="HISTORICAL", source="ci",
            content="token=abcdefghijklmnopqrstuvwxyz123456",
        )
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz123456", str(row))

    def test_550_profiles_unchanged(self):
        self.assertEqual(len(list_workers()), 550)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "ZULIP_SITE_URL": "https://example.zulipchat.com",
            "ZULIP_BOT_EMAIL": "bot@example.zulipchat.com",
            "ZULIP_API_KEY": "secret-test-key",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def _message(self, content="test"):
        return z.build_message(
            stream="system-operations", topic="Backend-health",
            message_type="health", data_status="HISTORICAL",
            source="existing_health", content=content,
        )

    def test_successful_publish_is_idempotent(self):
        row = self._message("idempotency")
        with patch.object(z, "_deliver", return_value={"status": "sent", "attempts": 1}) as deliver:
            first = z.publish(row)
            second = z.publish(row)
        self.assertEqual(first["status"], "sent")
        self.assertEqual(second["status"], "duplicate_suppressed")
        self.assertEqual(deliver.call_count, 1)

    def test_outage_queues_without_raising(self):
        row = self._message("outage")
        with patch.object(z, "_deliver", return_value={
            "status": "delivery_failed", "error_type": "ConnectError", "attempts": 3,
        }):
            result = z.publish(row)
        self.assertEqual(result["status"], "delivery_failed")
        self.assertGreaterEqual(z.status()["pending_count"], 1)

    def test_flush_retries_queue(self):
        row = self._message("flush")
        with patch.object(z, "_deliver", side_effect=[
            {"status": "delivery_failed", "error_type": "ConnectError"},
            {"status": "sent", "attempts": 1},
        ]):
            z.publish(row)
            result = z.flush_queue()
        self.assertEqual(result["sent"], 1)

    def test_rate_limit_retry_uses_retry_after(self):
        response = httpx.Response(429, headers={"Retry-After": "1"},
                                  request=httpx.Request("POST", "https://example.zulipchat.com"))
        with patch("app.zulip_notifier.httpx.post", side_effect=[response, httpx.Response(
            200, request=httpx.Request("POST", "https://example.zulipchat.com")
        )]), patch("app.zulip_notifier.time.sleep") as sleep:
            result = z._deliver(self._message("rate"))
        self.assertEqual(result["status"], "sent")
        sleep.assert_called_once_with(1.0)

    def test_task_seam_is_best_effort(self):
        with patch.object(z, "_deliver", return_value={"status": "sent"}):
            result = z.notify_task_result({
                "task_id": "t1", "worker_id": "worker_001", "status": "completed",
            })
        self.assertEqual(result["status"], "sent")
        self.assertEqual(z.notify_task_result({"status": "running"})["status"], "skipped")

    def test_market_message_seam_maps_supported_groups_only(self):
        with patch.object(z, "_deliver", return_value={"status": "sent"}):
            result = z.notify_market_message({
                "agent_id": "worker_001", "market_group": "crypto",
                "topic": "regime", "source_refs": ["source-1"],
            })
        self.assertEqual(result["status"], "sent")
        self.assertEqual(
            z.notify_market_message({"market_group": "gold"})["status"], "skipped"
        )


if __name__ == "__main__":
    unittest.main()
