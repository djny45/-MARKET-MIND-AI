"""Tests for the daily intelligence research cycle (offline, bounded)."""
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

os.environ["MARKET_MIND_DB"] = tempfile.mkdtemp() + "/daily-tests.db"

from app import daily_intelligence as di
from app.market_data import DataStatus


class IdentityAndSessionTests(unittest.TestCase):
    def test_stable_cycle_id(self):
        self.assertEqual(di.cycle_id("2026-11-26"), "daily-2026-11-26")
        self.assertEqual(
            di.cycle_id(datetime(2026, 11, 26, tzinfo=timezone.utc)), "daily-2026-11-26"
        )

    def test_previous_cycle_id_is_bounded(self):
        self.assertEqual(di.previous_cycle_id("daily-2026-11-26"), "daily-2026-11-25")
        with self.assertRaises(ValueError):
            di.previous_cycle_id("daily-2026-11-26", days=31)

    def test_exchange_timezones(self):
        self.assertEqual(di.session_for("us")["timezone"], "America/New_York")
        self.assertEqual(di.session_for("india")["timezone"], "Asia/Kolkata")
        self.assertEqual(di.session_for("crypto")["session"], "continuous")
        self.assertEqual(di.session_for("gold")["market_group"], "gold")


class ObservationTests(unittest.TestCase):
    def test_market_failure_is_unavailable_with_reason(self):
        with patch("app.four_market_terminal.build_terminal_snapshot",
                   side_effect=RuntimeError("offline")):
            row = di.collect_market_observation("us")
        self.assertEqual(row["data_status"], DataStatus.UNAVAILABLE.value)
        self.assertEqual(row["status_label"], "UNAVAILABLE")
        self.assertIn("unavailable", row["reason"].lower())
        self.assertIn("market_freshness", row)
        self.assertIn("data_status", row)

    def test_market_status_is_not_mislabelled_as_live(self):
        snapshot = {"markets": [{
            "market_status": "fresh", "headline": "FRESH",
            "usable_count": 5, "unavailable_count": 0, "stale_count": 0,
            "adapter": {"name": "yahoo-us-equities"},
            "quotes": [{"symbol": "AAPL", "status": "historical", "status_label": "HISTORICAL",
                        "timestamp": "2026-01-01T00:00:00Z",
                        "retrieved_at": "2026-01-01T00:00:01Z", "source": "yahoo-us-equities"}],
        }]}
        with patch("app.four_market_terminal.build_terminal_snapshot", return_value=snapshot):
            row = di.collect_market_observation("us")
        self.assertEqual(row["data_status"], "historical")
        self.assertEqual(row["market_freshness"], "fresh")
        self.assertEqual(row["observed_labels"], ["historical"])

    def test_gold_observation_is_tokenized_only(self):
        fake = type("Q", (), {"to_payload": lambda self: {
            "symbol": "PAXG", "status": "historical", "status_label": "HISTORICAL",
            "last": 3559.0, "source": "coingecko-gold-token",
            "timestamp": "2026-01-01T00:00:00Z",
            "retrieved_at": "2026-01-01T00:00:01Z",
        }})()
        with patch("app.exchange_intelligence.gold_token_quote", return_value=fake):
            row = di.collect_gold_observation()
        self.assertEqual(row["instrument_class"], "tokenized_gold")
        self.assertIn("not spot or futures", row["note"])


class AccountingAndScorecardTests(unittest.TestCase):
    def test_accounting_never_claims_550_active(self):
        row = di.execution_accounting()
        self.assertEqual(row["registered_agents"], 550)
        self.assertLessEqual(row["agents_executed_tasks"], row["registered_agents"])
        self.assertIn("NOT 550 active models", row["metric_definition"])

    def test_quality_scorecard_uses_only_verified_labels(self):
        cycle = {
            "observations": [
                {"market_group": "us", "data_status": "historical",
                 "usable_count": 5, "unavailable_count": 0, "stale_count": 0},
                {"market_group": "gold", "data_status": "unavailable",
                 "usable_count": 0, "unavailable_count": 1, "stale_count": 0},
            ],
            "execution": {"registered_agents": 550, "agents_executed_tasks": 2},
        }
        card = di.quality_scorecard(cycle)
        self.assertTrue(card["data_labels_verified"])
        self.assertEqual(card["usable_observations"], 5)
        self.assertAlmostEqual(card["observation_coverage"], 5 / 6, places=4)
        self.assertIsNotNone(card["agent_participation"])

    def test_consensus_is_descriptive_not_proof(self):
        result = di.consensus_from_findings([
            {"direction": "bullish"}, {"direction": "bullish"}, {"direction": "bearish"},
        ])
        self.assertTrue(result["available"])
        self.assertTrue(result["disagreement_present"])
        self.assertIn("not statistical consensus", result["data_note"])
        self.assertFalse(di.consensus_from_findings([])["available"])


class ArchiveTests(unittest.TestCase):
    def test_append_only_versions_and_parent_chain(self):
        first = di.run_daily_cycle(date="2026-11-20", publish_zulip=False)
        self.assertEqual(first["status"], "completed")
        revisions = first["archive"]["archived"]
        self.assertEqual(len(revisions), 5)
        self.assertTrue(all(row["revision"] == 1 for row in revisions))
        self.assertTrue(all(row["parent_sha256"] is None for row in revisions))

        second = di.run_daily_cycle(date="2026-11-21", publish_zulip=False)
        self.assertEqual(second["status"], "completed")
        comparison = di.compare_cycles("daily-2026-11-21", "daily-2026-11-20")
        self.assertEqual(len(comparison["comparisons"]), 5)
        self.assertIn("content hashes only", comparison["data_note"])

    def test_duplicate_cycle_is_suppressed(self):
        di.run_daily_cycle(date="2026-11-22", publish_zulip=False)
        duplicate = di.run_daily_cycle(date="2026-11-22", publish_zulip=False)
        self.assertEqual(duplicate["status"], "duplicate_suppressed")
        self.assertTrue(duplicate["duplicate_cycle_detected"])

    def test_archive_read_is_bounded(self):
        with self.assertRaises(ValueError):
            di.read_archive(limit=0)


class ZulipDigestTests(unittest.TestCase):
    def test_digest_is_one_consolidated_message(self):
        from app import zulip_notifier as z

        with patch.object(z, "_deliver", return_value={"status": "sent", "attempts": 1}) as deliver, \
             patch.dict(os.environ, {
                 "ZULIP_SITE_URL": "https://example.zulipchat.com",
                 "ZULIP_BOT_EMAIL": "bot@example.zulipchat.com",
                 "ZULIP_API_KEY": "secret-test-key",
             }):
            result = z.notify_daily_digest({
                "cycle_id": "daily-2026-11-26", "status": "partial",
                "quality_scorecard": {"usable_observations": 4,
                                      "unavailable_observations": 1, "stale_observations": 0},
                "execution": {"agents_executed_tasks": 2, "registered_agents": 550,
                              "tasks_completed": 3, "tasks_pending": 0},
                "observations": [{"market_group": "us", "data_status": "historical",
                                  "headline": "FRESH"}],
            })
        self.assertEqual(result["status"], "sent")
        self.assertEqual(deliver.call_count, 1)

    def test_zulip_outage_does_not_stop_cycle(self):
        with patch("app.daily_intelligence.archive_cycle",
                   return_value={"cycle_id": "x", "archived": []}), \
             patch("app.zulip_notifier.notify_daily_digest",
                   return_value={"status": "delivery_failed"}):
            result = di.run_daily_cycle(date="2026-11-23", publish_zulip=True)
        self.assertIn(result["status"], {"completed", "partial", "duplicate_suppressed"})
        self.assertEqual(result["zulip_notification"]["status"], "delivery_failed")


if __name__ == "__main__":
    unittest.main()
