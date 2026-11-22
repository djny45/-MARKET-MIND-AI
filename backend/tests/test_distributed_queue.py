import time
import unittest

from app.distributed_queue import (
    Job,
    JobStatus,
    QueueCapabilities,
    RetryPolicy,
    capabilities,
    idempotency_key_required,
    lease_deadline,
)


class DistributedQueueDesignTests(unittest.TestCase):
    def test_job_statuses_and_shape(self):
        job = Job(
            id="job-1",
            idempotency_key="key-1",
            queue_key="default",
            body={"research_only": True},
            worker_id="w1",
            status=JobStatus.QUEUED,
            attempts=0,
            created_at=time.time(),
        )
        self.assertEqual(job.status, JobStatus.QUEUED)
        self.assertTrue(job.idempotency_key)
        self.assertIsNone(job.parent_job_id)

    def test_idempotency_key_required(self):
        with self.assertRaises(ValueError):
            idempotency_key_required("")
        with self.assertRaises(ValueError):
            idempotency_key_required(None)
        self.assertEqual(idempotency_key_required("  key "), "key")

    def test_lease_deadline_bounds(self):
        deadline = lease_deadline(3600)
        self.assertGreater(deadline, time.time())
        with self.assertRaises(ValueError):
            lease_deadline(0)
        with self.assertRaises(ValueError):
            lease_deadline(86401)

    def test_retry_policy_validation(self):
        RetryPolicy().validate()
        with self.assertRaises(ValueError):
            RetryPolicy(max_attempts=0).validate()
        with self.assertRaises(ValueError):
            RetryPolicy(backoff_seconds=-1).validate()

    def test_capabilities_shape(self):
        caps = capabilities()
        self.assertIsInstance(caps, QueueCapabilities)
        self.assertTrue(caps.single_host_supported)
        self.assertFalse(caps.multi_host_supported)
        self.assertTrue(caps.idempotency)
        self.assertTrue(caps.deadletter)
        self.assertFalse(caps.broker_execution) if hasattr(caps, "broker_execution") else None
        self.assertTrue(caps.replication_needed_for_multi_host)


if __name__ == "__main__":
    unittest.main()
