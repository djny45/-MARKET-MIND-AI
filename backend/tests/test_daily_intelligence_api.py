"""API contract tests for daily intelligence routes."""
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ["MARKET_MIND_DB"] = tempfile.mkdtemp() + "/daily-api.db"
from fastapi.testclient import TestClient
from app.main import app


class DailyApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_status_is_available_and_redacted(self):
        body = self.client.get("/api/daily/status").json()
        self.assertEqual(body["mode"], "daily_intelligence_research_cycle")
        self.assertFalse(body["zulip"]["credentials_exposed"])
        self.assertFalse(body["execution"]["broker_execution"])

    def test_run_creates_archive_and_honest_accounting(self):
        body = self.client.post("/api/daily/run", json={
            "date": "2026-11-19", "publish_zulip": False,
        }).json()
        self.assertIn(body["status"], {"completed", "partial"})
        self.assertEqual(len(body["observations"]), 5)
        self.assertTrue(body["quality_scorecard"]["data_labels_verified"])
        accounting = body["execution"]
        self.assertEqual(accounting["registered_agents"], 550)
        self.assertLessEqual(accounting["agents_executed_tasks"], 550)
        self.assertEqual(len(body["archive"]["archived"]), 5)

    def test_duplicate_run_is_suppressed(self):
        self.client.post("/api/daily/run", json={
            "date": "2026-11-18", "publish_zulip": False,
        })
        second = self.client.post("/api/daily/run", json={
            "date": "2026-11-18", "publish_zulip": False,
        }).json()
        self.assertEqual(second["status"], "duplicate_suppressed")

    def test_archive_and_compare(self):
        self.client.post("/api/daily/run", json={
            "date": "2026-11-17", "publish_zulip": False,
        })
        self.client.post("/api/daily/run", json={
            "date": "2026-11-16", "publish_zulip": False,
        })
        archive = self.client.get("/api/daily/archive?cycle_id=daily-2026-11-17").json()
        self.assertEqual(archive["count"], 5)
        compare = self.client.get("/api/daily/compare", params={
            "cycle_id": "daily-2026-11-17", "previous_cycle_id": "daily-2026-11-16",
        }).json()
        self.assertEqual(len(compare["comparisons"]), 5)

    def test_invalid_limit_rejected(self):
        response = self.client.get("/api/daily/archive?limit=0")
        self.assertEqual(response.status_code, 400)

    def test_digest_reuses_existing_zulip_adapter(self):
        with patch("app.zulip_notifier._deliver",
                   return_value={"status": "sent", "attempts": 1}) as deliver, \
             patch.dict(os.environ, {
                 "ZULIP_SITE_URL": "https://example.zulipchat.com",
                 "ZULIP_BOT_EMAIL": "bot@example.zulipchat.com",
                 "ZULIP_API_KEY": "test-key",
             }):
            body = self.client.post("/api/daily/run", json={
                "date": "2026-11-15", "publish_zulip": True,
            }).json()
        self.assertEqual(body["zulip_notification"]["status"], "sent")
        self.assertEqual(deliver.call_count, 1)


if __name__ == "__main__":
    unittest.main()
