import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.research_checkpoint_store import ResearchCheckpointStore


class ResearchCheckpointStoreTests(unittest.TestCase):
    def test_checkpoint_survives_store_reopen_and_links_revisions(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "checkpoints.sqlite"
            first_store = ResearchCheckpointStore(database)
            first = first_store.save("task-1", {"phase": "collect", "items": [1, 2]})
            first_store.close()

            second_store = ResearchCheckpointStore(database)
            latest = second_store.get_latest("task-1")
            self.assertEqual(latest["revision"], 1)
            self.assertEqual(latest["checkpoint_id"], first["checkpoint_id"])
            second = second_store.save(
                "task-1", {"phase": "synthesize", "items": [1, 2, 3]},
                expected_revision=latest["revision"],
            )
            restored = second_store.get_latest("task-1")
            self.assertEqual(restored["revision"], 2)
            self.assertEqual(restored["parent_checkpoint_id"], first["checkpoint_id"])
            self.assertEqual(restored["checkpoint_id"], second["checkpoint_id"])
            self.assertEqual(restored["payload"]["phase"], "synthesize")
            second_store.close()

    def test_compare_and_swap_rejects_stale_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ResearchCheckpointStore(Path(directory) / "checkpoints.sqlite")
            store.save("task-2", {"step": 1})
            with self.assertRaisesRegex(ValueError, "revision conflict"):
                store.save("task-2", {"step": "stale"}, expected_revision=0)
            self.assertEqual(store.get_latest("task-2")["payload"], {"step": 1})

    def test_integrity_check_rejects_payload_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "checkpoints.sqlite"
            store = ResearchCheckpointStore(database)
            saved = store.save("task-3", {"status": "safe"})
            with sqlite3.connect(database) as db:
                db.execute(
                    "UPDATE research_checkpoints SET payload_json=? WHERE checkpoint_id=?",
                    (json.dumps({"status": "tampered"}), saved["checkpoint_id"]),
                )
            with self.assertRaisesRegex(ValueError, "integrity ID"):
                store.get_latest("task-3")

    def test_integrity_check_rejects_broken_parent_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "checkpoints.sqlite"
            store = ResearchCheckpointStore(database)
            first = store.save("task-4", {"step": 1})
            second = store.save("task-4", {"step": 2}, expected_revision=1)
            with sqlite3.connect(database) as db:
                db.execute(
                    "UPDATE research_checkpoints SET parent_checkpoint_id=? WHERE checkpoint_id=?",
                    ("wrong-parent", second["checkpoint_id"]),
                )
            with self.assertRaisesRegex(ValueError, "parent chain"):
                store.get_latest("task-4")
            self.assertIsNotNone(first)

    def test_rejects_invalid_task_payload_and_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ResearchCheckpointStore(Path(directory) / "checkpoints.sqlite")
            for task_id, payload, revision in (
                ("", {}, 0), ("task", [], 0), ("task", {"x": float("nan")}, 0),
                ("task", {}, True), ("task", {}, -1),
            ):
                with self.subTest(task_id=task_id, payload=payload, revision=revision):
                    with self.assertRaises(ValueError):
                        store.save(task_id, payload, expected_revision=revision)

    def test_unknown_task_has_no_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ResearchCheckpointStore(Path(directory) / "checkpoints.sqlite")
            self.assertIsNone(store.get_latest("missing"))

    def test_in_memory_store_and_close_semantics(self):
        store = ResearchCheckpointStore(":memory:")
        saved = store.save("task-memory", {"step": "one"})
        self.assertEqual(store.get_latest("task-memory")["checkpoint_id"], saved["checkpoint_id"])
        store.close()
        store.close()
        with self.assertRaisesRegex(RuntimeError, "store is closed"):
            store.get_latest("task-memory")


if __name__ == "__main__":
    unittest.main()
