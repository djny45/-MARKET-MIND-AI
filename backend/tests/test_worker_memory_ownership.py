"""Worker notes are durable and their per-user ownership survives a restart."""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from app.authorization import ResourceRef, OwnershipRegistry, authorize, ownership_registry
from app.worker_memory import append_memory, read_memory


class WorkerMemoryOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {
            "MARKET_MIND_DB": os.path.join(self.temp.name, "memory.db")
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        ownership_registry.clear()
        self.addCleanup(ownership_registry.clear)

    def test_memory_claim_survives_a_new_registry_instance(self):
        note = append_memory("worker_001", "observation", {"summary": "historical note"})
        ownership_registry.record("memory", note["memory_id"], "alice")
        restarted = OwnershipRegistry()
        self.assertEqual(restarted.owner_of("memory", note["memory_id"]), "alice")
        self.assertEqual(read_memory("worker_001")["count"], 1)

    def test_cross_user_memory_access_is_denied_by_default(self):
        note = append_memory("worker_001", "observation", {"summary": "private note"})
        ref = ResourceRef("memory", note["memory_id"])
        ownership_registry.record("memory", note["memory_id"], "alice")
        self.assertTrue(authorize({"username": "alice", "role": "viewer"}, "viewer", resource=ref).allowed)
        self.assertFalse(authorize({"username": "bob", "role": "viewer"}, "viewer", resource=ref).allowed)
        self.assertTrue(authorize({"username": "admin", "role": "admin"}, "viewer", resource=ref).allowed)

    def test_unclaimed_memory_id_is_not_publicly_accessible(self):
        ref = ResourceRef("memory", "never-claimed")
        decision = authorize({"username": "bob", "role": "viewer"}, "viewer", resource=ref)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "unregistered_resource")


if __name__ == "__main__":
    unittest.main()
