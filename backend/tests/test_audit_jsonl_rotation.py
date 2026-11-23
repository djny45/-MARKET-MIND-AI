"""Size-capped rotation for the append-only research audit logs.

These logs are the one artefact in the platform with no retention policy: before
this module they grew without bound on a long-running host.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.audit_jsonl import append_record, limits, log_stats, read_records, rotate


class AuditJsonlRotationTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.root = Path(self._dir.name)
        self.log = self.root / "shadow_tracker_audit.jsonl"

    def tearDown(self):
        self._dir.cleanup()

    def _records(self, path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def test_appends_one_json_object_per_line(self):
        append_record(self.log, {"event": "a", "n": 1})
        append_record(self.log, {"event": "b", "n": 2})
        self.assertEqual(self._records(self.log), [{"event": "a", "n": 1}, {"event": "b", "n": 2}])

    def test_no_rotation_below_the_cap(self):
        result = append_record(self.log, {"event": "a"}, max_bytes=10_000, keep=3)
        self.assertEqual(result["rotated"], [])
        self.assertEqual(log_stats(self.log)["archives"], [])

    def test_rotation_preserves_ordering_and_evidence_per_run(self):
        for index in range(4):
            append_record(self.log, {"n": index, "pad": "x" * 40}, max_bytes=150, keep=2)
        archives = sorted(path.name for path in self.root.glob(f"{self.log.name}.*"))
        self.assertLessEqual(len(archives), 2)
        ordered = []
        for name in sorted(archives, reverse=True):
            ordered.extend(record["n"] for record in self._records(self.root / name))
        ordered.extend(record["n"] for record in self._records(self.log))
        self.assertEqual(ordered, sorted(ordered))
        self.assertEqual(ordered[-1], 3)

    def test_retention_bound_is_enforced(self):
        for index in range(10):
            append_record(self.log, {"n": index, "pad": "x" * 40}, max_bytes=150, keep=2)
        archives = sorted(path.name for path in self.root.glob(f"{self.log.name}.*"))
        self.assertLessEqual(len(archives), 2)
        self.assertFalse((self.root / f"{self.log.name}.3").exists())

    def test_rotation_is_per_file_and_never_touches_other_logs(self):
        other = self.root / "skill_cadence_audit.jsonl"
        append_record(other, {"keep": True})
        for index in range(4):
            append_record(self.log, {"n": index, "pad": "x" * 40}, max_bytes=120, keep=1)
        self.assertEqual(self._records(other), [{"keep": True}])

    def test_env_limits_are_read_and_validated(self):
        previous = {key: os.environ.get(key) for key in
                    ("MARKET_MIND_AUDIT_LOG_MAX_BYTES", "MARKET_MIND_AUDIT_LOG_KEEP")}
        try:
            os.environ["MARKET_MIND_AUDIT_LOG_MAX_BYTES"] = "65536"
            os.environ["MARKET_MIND_AUDIT_LOG_KEEP"] = "5"
            self.assertEqual(limits(), (65536, 5))
            os.environ["MARKET_MIND_AUDIT_LOG_MAX_BYTES"] = "not-a-number"
            os.environ["MARKET_MIND_AUDIT_LOG_KEEP"] = "0"
            max_bytes, keep = limits()
            self.assertGreaterEqual(max_bytes, 1024)
            self.assertGreaterEqual(keep, 1)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_rotate_on_missing_file_is_a_no_op(self):
        self.assertEqual(rotate(self.root / "absent.jsonl", keep=3), [])

    def test_log_stats_reports_active_and_archive_bytes(self):
        append_record(self.log, {"n": 1})
        append_record(self.log, {"n": 2, "pad": "y" * 80}, max_bytes=60, keep=2)
        stats = log_stats(self.log)
        self.assertGreater(stats["active_bytes"], 0)
        self.assertEqual(len(stats["archives"]), 1)
        self.assertEqual(stats["total_bytes"],
                         stats["active_bytes"] + stats["archives"][0]["bytes"])

    def test_read_records_spans_archives_in_order(self):
        for index in range(6):
            append_record(self.log, {"n": index, "pad": "z" * 40}, max_bytes=150, keep=5)
        self.assertTrue((self.log.parent / f"{self.log.name}.1").exists())
        self.assertEqual([record["n"] for record in read_records(self.log)], list(range(6)))

    def test_truncated_final_line_does_not_break_readers(self):
        append_record(self.log, {"n": 1})
        with open(self.log, "a", encoding="utf-8") as handle:
            handle.write('{"n": 2, "pad": "half-writ')
        self.assertEqual([record["n"] for record in read_records(self.log)], [1])
        append_record(self.log, {"n": 3})
        self.assertEqual([record["n"] for record in read_records(self.log)], [1, 3])


class AuditLogsStayReadableTests(unittest.TestCase):
    """Readers must still see events after the writers rotate."""

    def test_shadow_session_log_stays_parseable_after_rotation(self):
        from app.research_shadow_session import (
            ShadowSessionEngine,
            make_backtest_config,
            shadow_metrics_from_log,
        )

        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "research_shadow_log.jsonl"
            engine = ShadowSessionEngine(make_backtest_config(), log_path=log_path)
            engine.begin_run("run-1")
            for index in range(5):
                engine.record_shadow_order({
                    "symbol": "BTC-USD",
                    "side": "BUY",
                    "quantity": 0.01,
                    "reference_price": 30_000.0 + index,
                    "timestamp": f"2026-01-0{index + 1}T00:00:00Z",
                }, run_id="run-1")
            for line in log_path.read_text(encoding="utf-8").splitlines():
                self.assertIsInstance(json.loads(line), dict)
            metrics = shadow_metrics_from_log(log_path)
            self.assertEqual(metrics["shadow_orders"], 5)
            self.assertEqual(metrics["executed_orders"], 0)

    def test_shadow_metrics_survive_rotation(self):
        """Rotating an audit log must not make previously recorded events vanish."""
        from app import audit_jsonl
        from app.research_shadow_session import (
            ShadowSessionEngine,
            make_backtest_config,
            shadow_metrics_from_log,
        )

        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "research_shadow_log.jsonl"
            engine = ShadowSessionEngine(make_backtest_config(), log_path=log_path)
            engine.begin_run("run-rot")
            capped = lambda path, record, **kw: audit_jsonl.append_record(
                path, record, max_bytes=400, keep=10)
            with mock.patch("app.research_shadow_session.append_record", capped):
                for index in range(6):
                    engine.record_shadow_order({
                        "symbol": "ETH-USD",
                        "side": "BUY",
                        "quantity": 0.1,
                        "reference_price": 2_000.0 + index,
                        "timestamp": f"2026-02-0{index + 1}T00:00:00Z",
                    }, run_id="run-rot")
            self.assertTrue(list(log_path.parent.glob(f"{log_path.name}.*")))
            self.assertEqual(shadow_metrics_from_log(log_path)["shadow_orders"], 6)


if __name__ == "__main__":
    unittest.main()
