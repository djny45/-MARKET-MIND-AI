import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.auth_crypto import hash_password, hash_session_token
from app import user_auth
from app.user_session_middleware import UserSessionAuthMiddleware


class UserSessionAuthMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def _call(self, path="/api/workers", method="GET", cookies="", csrf="", origin=""):
        captured = {"status": None}

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            if message["type"] == "http.response.start":
                captured["status"] = message["status"]

        headers = []
        if cookies:
            headers.append((b"cookie", cookies.encode()))
        if csrf:
            headers.append((b"x-csrf-token", csrf.encode()))
        if origin:
            headers.append((b"origin", origin.encode()))
        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
            "query_string": b"", "headers": headers, "server": ("test", 80),
            "client": ("127.0.0.1", 1234),
        }
        await UserSessionAuthMiddleware(app)(scope, receive, send)
        return captured["status"]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "auth.db"
        users = json.dumps([{
            "username": "admin",
            "password_hash": hash_password("a long test password"),
            "role": "admin",
        }])
        self.env = {
            "MARKET_MIND_USER_AUTH": "true",
            "MARKET_MIND_USERS": users,
            "MARKET_MIND_DB": str(self.db),
        }
        self.session = user_auth.create_user_session({"username": "admin", "role": "admin"}, self.env)
        self.cookies = f"mm_session={self.session['session_token']}; mm_csrf={self.session['csrf_token']}"

    def tearDown(self):
        self.tmp.cleanup()

    async def test_disabled_middleware_is_a_noop(self):
        with patch.dict(os.environ, {"MARKET_MIND_USER_AUTH": "false"}, clear=False):
            self.assertEqual(await self._call(), 204)

    async def test_missing_session_is_rejected(self):
        with patch.dict(os.environ, self.env, clear=False):
            self.assertEqual(await self._call(), 401)

    async def test_valid_session_is_accepted(self):
        with patch.dict(os.environ, self.env, clear=False):
            self.assertEqual(await self._call(cookies=self.cookies), 204)

    async def test_write_requires_csrf(self):
        with patch.dict(os.environ, self.env, clear=False):
            self.assertEqual(
                await self._call(method="POST", cookies=self.cookies), 403
            )
            self.assertEqual(
                await self._call(method="POST", cookies=self.cookies, csrf=self.session["csrf_token"]),
                204,
            )

    async def test_strict_mode_requires_origin_on_writes(self):
        env = dict(self.env, ENV_VALIDATION_STRICT="1", FRONTEND_ORIGINS="https://app.example")
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(
                await self._call(method="POST", cookies=self.cookies, csrf=self.session["csrf_token"]),
                403,
            )
            self.assertEqual(
                await self._call(
                    method="POST", cookies=self.cookies,
                    csrf=self.session["csrf_token"], origin="https://app.example",
                ),
                204,
            )

    async def test_untrusted_forwarded_headers_are_stripped_by_default(self):
        from backend.app.user_session_middleware import _FORWARDED_HEADERS, _strip_untrusted_forwarded_headers
        for name in _FORWARDED_HEADERS:
            scope = {
                "headers": [(b"x-forwarded-for", b"10.9.8.7"), (name, b"custom")],
                "client": ("127.0.0.1", 1234),
            }
            _strip_untrusted_forwarded_headers(scope)
            remaining = [n for n, _ in scope["headers"]]
            self.assertNotIn(name, remaining)
        with patch.dict(os.environ, {"MARKET_MIND_TRUSTED_PROXY_COUNT": "2"}):
            scope = {"headers": [(b"x-forwarded-for", b"10.9.8.7")], "client": ("127.0.0.1", 1234)}
            _strip_untrusted_forwarded_headers(scope)
            self.assertTrue(any(n == b"x-forwarded-for" for n, _ in scope["headers"]))

    async def test_expired_session_is_rejected_at_http_layer(self):
        import sqlite3
        with sqlite3.connect(self.env["MARKET_MIND_DB"]) as db:
            db.execute(
                "UPDATE auth_sessions SET idle_expires_at=? WHERE session_token_hash=?",
                (0, hash_session_token(self.session["session_token"])),
            )
        with patch.dict(os.environ, self.env, clear=False):
            self.assertEqual(await self._call(cookies=self.cookies), 401)

    async def test_health_and_login_are_exempt(self):
        with patch.dict(os.environ, self.env, clear=False):
            self.assertEqual(await self._call(path="/api/health"), 204)
            self.assertEqual(await self._call(path="/api/auth/login", method="POST"), 204)


if __name__ == "__main__":
    unittest.main()
