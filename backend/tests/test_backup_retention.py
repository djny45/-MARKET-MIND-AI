import tempfile
import unittest
from pathlib import Path

from backup_retention import plan_retention, prune_backups


class BackupRetentionTests(unittest.TestCase):
    def _backups(self, directory, count):
        for day in range(1, count + 1):
            (directory / f"market_mind-202611{day:02d}T010203Z.db").write_bytes(b"backup")

    def test_dry_run_lists_expired_without_deleting(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            self._backups(directory, 5)
            result = prune_backups(directory, keep=2)
            self.assertEqual(result["mode"], "dry-run")
            self.assertEqual(len(result["retained"]), 2)
            self.assertEqual(len(result["expired"]), 3)
            self.assertEqual(len(list(directory.iterdir())), 5)

    def test_apply_deletes_only_expired_matching_backups(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            self._backups(directory, 4)
            unrelated = directory / "notes.txt"
            unrelated.write_text("keep", encoding="utf-8")
            result = prune_backups(directory, keep=2, apply=True)
            self.assertEqual(len(result["deleted"]), 2)
            self.assertTrue(unrelated.exists())
            self.assertEqual(len(list(directory.glob("market_mind-*.db"))), 2)

    def test_rejects_zero_retention(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "keep_must_be_at_least_one"):
                plan_retention(Path(temp), keep=0)

    def test_rejects_matching_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            target = directory / "outside.db"
            target.write_bytes(b"do not delete")
            link = directory / "market_mind-20261101T010203Z.db"
            link.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "regular_file"):
                plan_retention(directory)
            self.assertTrue(target.exists())


if __name__ == "__main__":
    unittest.main()
