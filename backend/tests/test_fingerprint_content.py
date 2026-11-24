"""Fingerprints must detect equal-count/different-value restores and FK errors."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from dr_common import database_fingerprint  # noqa: E402
from restore_orchestrator import _compare  # noqa: E402


def _database(path: Path, close_value: float) -> Path:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE market_bars (symbol TEXT, close REAL)")
        connection.execute("INSERT INTO market_bars VALUES ('AAPL', ?)", (close_value,))
        connection.execute(
            "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT)"
        )
        connection.execute("INSERT INTO schema_migrations VALUES (1, '2026-01-01')")
    return path


class FingerprintContentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_equal_row_counts_with_different_values_are_detected(self):
        left = database_fingerprint(_database(self.root / "a.db", 10.0))
        right = database_fingerprint(_database(self.root / "b.db", 11.0))
        self.assertEqual(left["table_counts"], right["table_counts"])
        self.assertNotEqual(left["content_digest"], right["content_digest"])
        comparison = _compare(right, {"fingerprint": left})
        self.assertEqual(comparison["status"], "mismatch")
        self.assertFalse(comparison["content_match"])

    def test_identical_fk_violations_do_not_break_parity(self):
        fingerprint = {
            "table_counts": {"child": 1}, "schema_version": 1,
            "content_digest": "same", "foreign_key_violations": ["orphan-child"],
        }
        result = _compare(dict(fingerprint), {"fingerprint": dict(fingerprint)})
        self.assertEqual(result["status"], "matched")
        self.assertTrue(result["foreign_key_ok"])

    def test_new_fk_violation_on_restore_is_a_mismatch(self):
        expected = {"table_counts": {"child": 1}, "schema_version": 1,
                    "content_digest": "same", "foreign_key_violations": []}
        restored = dict(expected, foreign_key_violations=["orphan-child"])
        result = _compare(restored, {"fingerprint": expected})
        self.assertEqual(result["status"], "mismatch")
        self.assertFalse(result["foreign_key_ok"])

    def test_foreign_key_violations_are_recorded(self):
        path = self.root / "fk.db"
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
            connection.execute(
                "CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER "
                "REFERENCES parent(id))"
            )
            connection.execute("INSERT INTO child VALUES (1, 999)")
        fingerprint = database_fingerprint(path)
        self.assertTrue(fingerprint["foreign_key_violations"])


if __name__ == "__main__":
    unittest.main()
