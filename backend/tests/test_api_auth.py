import os
import unittest
from unittest.mock import patch

from app.api_auth import ResearchAPIAuthMiddleware


class ResearchAPIAuthMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def _call(self, path="/api/private", method="GET", headers=None, env=None):
        captured = {"status": None, "body": b""}

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            if message["type"] == "http.response.start":
                captured["status"] = message["status"]
            elif message["type"] == "http.response.body":
                captured["body"] += message.get("body", b"")

        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
            "query_string": b"", "headers": headers or [], "server": ("test", 80),
            "client": ("127.0.0.1", 1234),
        }
        with patch.dict(os.environ, env or {}, clear=False):
            await ResearchAPIAuthMiddleware(app)(scope, receive, send)
        return captured

    async def test_auth_disabled_preserves_local_development(self):
        result = await self._call(env={"API_AUTH_REQUIRED": "false"})
        self.assertEqual(result["status"], 204)

    async def test_missing_server_token_fails_closed(self):
        result = await self._call(env={"API_AUTH_REQUIRED": "true", "API_AUTH_TOKEN": ""})
        self.assertEqual(result["status"], 503)

    async def test_missing_and_invalid_bearer_tokens_are_rejected(self):
        env = {"API_AUTH_REQUIRED": "true", "API_AUTH_TOKEN": "s" * 48}
        missing = await self._call(env=env)
        invalid = await self._call(headers=[(b"authorization", b"Bearer wrong")], env=env)
        self.assertEqual(missing["status"], 401)
        self.assertEqual(invalid["status"], 401)

    async def test_valid_bearer_token_is_accepted(self):
        token = "s" * 48
        result = await self._call(
            headers=[(b"authorization", f"Bearer {token}".encode())],
            env={"API_AUTH_REQUIRED": "true", "API_AUTH_TOKEN": token},
        )
        self.assertEqual(result["status"], 204)

    async def test_health_readiness_and_cors_preflight_are_exempt(self):
        env = {"API_AUTH_REQUIRED": "true", "API_AUTH_TOKEN": "s" * 48}
        health = await self._call(path="/api/health", env=env)
        ready = await self._call(path="/api/ready", env=env)
        preflight = await self._call(method="OPTIONS", env=env)
        self.assertEqual(health["status"], 204)
        self.assertEqual(ready["status"], 204)
        self.assertEqual(preflight["status"], 204)


if __name__ == "__main__":
    unittest.main()
