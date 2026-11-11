import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.auth_session_store import (
    create_session,
    get_session,
    initialize_auth_store,
    purge_expired_sessions,
    revoke_session,
)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class AuthSessionStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "private" / "auth.sqlite3"
        initialize_auth_store(self.database_path)
        self.session_hash = digest("opaque-session-token")
        self.csrf_hash = digest("opaque-csrf-token")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_persists_only_digests_and_returns_expiry(self):
        result = create_session(
            self.database_path,
            self.session_hash,
            self.csrf_hash,
            now=1000,
            idle_ttl_seconds=300,
            absolute_ttl_seconds=3600,
        )
        self.assertEqual(result["idle_expires_at"], 1300)
        self.assertEqual(result["absolute_expires_at"], 4600)

        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT session_token_hash, csrf_token_hash FROM auth_sessions"
            ).fetchone()
        self.assertEqual(row, (self.session_hash, self.csrf_hash))
        self.assertNotIn("opaque-session-token", repr(row))
        self.assertNotIn("opaque-csrf-token", repr(row))

    def test_read_slides_idle_expiry_but_never_absolute_expiry(self):
        create_session(
            self.database_path,
            self.session_hash,
            self.csrf_hash,
            now=1000,
            idle_ttl_seconds=300,
            absolute_ttl_seconds=1000,
        )
        active = get_session(
            self.database_path, self.session_hash, now=1200, idle_ttl_seconds=300
        )
        self.assertIsNotNone(active)
        self.assertEqual(active["last_seen_at"], 1200)
        self.assertEqual(active["idle_expires_at"], 1500)
        self.assertEqual(active["absolute_expires_at"], 2000)

        clock_rollback = get_session(
            self.database_path, self.session_hash, now=1100, idle_ttl_seconds=300
        )
        self.assertIsNotNone(clock_rollback)
        self.assertEqual(clock_rollback["last_seen_at"], 1200)

        still_active = get_session(
            self.database_path, self.session_hash, now=1600, idle_ttl_seconds=300
        )
        self.assertIsNotNone(still_active)
        self.assertEqual(still_active["idle_expires_at"], 1900)
        capped = get_session(
            self.database_path, self.session_hash, now=1900, idle_ttl_seconds=300
        )
        self.assertIsNotNone(capped)
        self.assertEqual(capped["idle_expires_at"], 2000)
        self.assertIsNone(
            get_session(
                self.database_path, self.session_hash, now=2000, idle_ttl_seconds=300
            )
        )

    def test_idle_and_absolute_expiry_fail_closed(self):
        create_session(
            self.database_path,
            self.session_hash,
            self.csrf_hash,
            now=1000,
            idle_ttl_seconds=100,
            absolute_ttl_seconds=500,
        )
        self.assertIsNone(
            get_session(
                self.database_path, self.session_hash, now=1100, idle_ttl_seconds=100
            )
        )
        self.assertIsNone(
            get_session(
                self.database_path, self.session_hash, now=1101, idle_ttl_seconds=100
            )
        )

    def test_revoke_is_idempotent_and_prevents_future_reads(self):
        create_session(
            self.database_path,
            self.session_hash,
            self.csrf_hash,
            now=1000,
            idle_ttl_seconds=300,
            absolute_ttl_seconds=1000,
        )
        self.assertTrue(
            revoke_session(self.database_path, self.session_hash, now=1050)
        )
        self.assertFalse(
            revoke_session(self.database_path, self.session_hash, now=1051)
        )
        self.assertIsNone(
            get_session(
                self.database_path, self.session_hash, now=1052, idle_ttl_seconds=300
            )
        )

    def test_purge_removes_revoked_and_expired_rows(self):
        second_hash = digest("second-session")
        create_session(
            self.database_path,
            self.session_hash,
            self.csrf_hash,
            now=1000,
            idle_ttl_seconds=100,
            absolute_ttl_seconds=500,
        )
        create_session(
            self.database_path,
            second_hash,
            self.csrf_hash,
            now=1000,
            idle_ttl_seconds=300,
            absolute_ttl_seconds=1000,
        )
        revoke_session(self.database_path, second_hash, now=1050)
        self.assertEqual(purge_expired_sessions(self.database_path, now=1100), 2)

    def test_rejects_empty_database_path(self):
        with self.assertRaises(ValueError):
            initialize_auth_store("")

    def test_rejects_invalid_digests_and_ttls(self):
        with self.assertRaises(ValueError):
            create_session(
                self.database_path,
                "raw-token",
                self.csrf_hash,
                now=1000,
                idle_ttl_seconds=100,
                absolute_ttl_seconds=500,
            )
        with self.assertRaises(ValueError):
            create_session(
                self.database_path,
                self.session_hash,
                self.csrf_hash,
                now=1000,
                idle_ttl_seconds=True,
                absolute_ttl_seconds=500,
            )


if __name__ == "__main__":
    unittest.main()
