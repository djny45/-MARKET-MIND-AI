import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.auth_crypto import hash_password
from app import user_auth


class UserAuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "auth.db"
        self.password_hash = hash_password("correct horse battery staple")
        self.users = json.dumps([{
            "username": "admin", "password_hash": self.password_hash, "role": "admin"
        }])
        self.env = {
            "MARKET_MIND_USER_AUTH": "true",
            "MARKET_MIND_USERS": self.users,
            "MARKET_MIND_DB": str(self.db),
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_disabled_by_default(self):
        self.assertFalse(user_auth.enabled({}))
        self.assertTrue(user_auth.enabled(self.env))

    def test_user_parsing_skips_invalid_entries(self):
        env = dict(self.env, MARKET_MIND_USERS=json.dumps([
            {"username": "ok", "password_hash": "h", "role": "viewer"},
            {"username": "bad", "password_hash": "h", "role": "superuser"},
            {"username": "", "password_hash": "h", "role": "admin"},
        ]))
        users = user_auth.load_users(env)
        self.assertEqual(set(users), {"ok"})

    def test_authenticate_checks_password_and_role(self):
        self.assertEqual(
            user_auth.authenticate("admin", "correct horse battery staple", self.env),
            {"username": "admin", "role": "admin"},
        )
        self.assertIsNone(user_auth.authenticate("admin", "wrong", self.env))
        self.assertIsNone(user_auth.authenticate("missing", "x", self.env))

    def test_session_lifecycle_and_csrf(self):
        session = user_auth.create_user_session({"username": "admin", "role": "admin"}, self.env)
        self.assertTrue(self.db.is_file())
        loaded = user_auth.get_user_session(session["session_token"], self.env)
        self.assertEqual(loaded["username"], "admin")
        self.assertEqual(loaded["role"], "admin")
        self.assertTrue(user_auth.csrf_matches(session["csrf_token"], loaded))
        self.assertFalse(user_auth.csrf_matches("bad", loaded))
        self.assertTrue(user_auth.revoke_user_session(session["session_token"], self.env))
        self.assertIsNone(user_auth.get_user_session(session["session_token"], self.env))

    def test_live_session_role_reflects_config_demotion_and_removal(self):
        session = user_auth.create_user_session({"username": "admin", "role": "admin"}, self.env)
        demoted = dict(self.env, MARKET_MIND_USERS=json.dumps([{
            "username": "admin", "password_hash": self.password_hash, "role": "viewer"
        }]))
        loaded = user_auth.get_user_session(session["session_token"], demoted)
        self.assertEqual(loaded["role"], "viewer")
        removed = dict(self.env, MARKET_MIND_USERS=json.dumps([{
            "username": "other", "password_hash": self.password_hash, "role": "admin"
        }]))
        self.assertIsNone(user_auth.get_user_session(session["session_token"], removed))
        # No configured users at all: keep the stored role as a safe fallback.
        fallback_env = {k: v for k, v in self.env.items() if k != "MARKET_MIND_USERS"}
        fallback = user_auth.get_user_session(session["session_token"], fallback_env)
        self.assertEqual(fallback["role"], "admin")

    def test_role_hierarchy(self):
        self.assertTrue(user_auth.role_allows("admin", "operator"))
        self.assertTrue(user_auth.role_allows("operator", "operator"))
        self.assertFalse(user_auth.role_allows("viewer", "operator"))


if __name__ == "__main__":
    unittest.main()
