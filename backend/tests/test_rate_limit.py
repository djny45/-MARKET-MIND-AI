import os
import unittest
from unittest.mock import patch

from app.rate_limit import RateLimitMiddleware


class RateLimitMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def _call(self, middleware, path="/api/private", headers=()):
        captured = {"status": None}

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            if message["type"] == "http.response.start":
                captured["status"] = message["status"]

        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": "GET", "scheme": "http", "path": path, "raw_path": path.encode(),
            "query_string": b"", "headers": list(headers), "server": ("test", 80),
            "client": ("127.0.0.1", 1234),
        }
        middleware.app = app
        await middleware(scope, receive, send)
        return captured["status"]

    async def test_trusted_proxy_forwarded_for_creates_distinct_buckets(self):
        middleware = RateLimitMiddleware(None)
        env = {
            "API_RATE_LIMIT_PER_MINUTE": "1",
            "MARKET_MIND_TRUSTED_PROXY_COUNT": "1",
        }
        with patch.dict(os.environ, env):
            self.assertEqual(await self._call(middleware, headers=[(b"x-forwarded-for", b"10.0.0.1")]), 204)
            self.assertEqual(await self._call(middleware, headers=[(b"x-forwarded-for", b"10.0.0.2")]), 204)
            self.assertEqual(await self._call(middleware, headers=[(b"x-forwarded-for", b"10.0.0.1")]), 429)

    async def test_disabled_by_default(self):
        middleware = RateLimitMiddleware(None)
        with patch.dict(os.environ, {"API_RATE_LIMIT_PER_MINUTE": "0"}):
            self.assertEqual(await self._call(middleware), 204)

    async def test_limit_is_enforced_per_client(self):
        middleware = RateLimitMiddleware(None)
        with patch.dict(os.environ, {"API_RATE_LIMIT_PER_MINUTE": "2"}):
            self.assertEqual(await self._call(middleware), 204)
            self.assertEqual(await self._call(middleware), 204)
            self.assertEqual(await self._call(middleware), 429)

    async def test_health_is_exempt(self):
        middleware = RateLimitMiddleware(None)
        with patch.dict(os.environ, {"API_RATE_LIMIT_PER_MINUTE": "1"}):
            self.assertEqual(await self._call(middleware, "/api/health"), 204)
            self.assertEqual(await self._call(middleware, "/api/health"), 204)

    async def test_invalid_configuration_disables_limiting(self):
        middleware = RateLimitMiddleware(None)
        with patch.dict(os.environ, {"API_RATE_LIMIT_PER_MINUTE": "not-a-number"}):
            self.assertEqual(await self._call(middleware), 204)
            self.assertEqual(await self._call(middleware), 204)

    async def test_reset_clears_state(self):
        middleware = RateLimitMiddleware(None)
        with patch.dict(os.environ, {"API_RATE_LIMIT_PER_MINUTE": "1"}):
            self.assertEqual(await self._call(middleware), 204)
            middleware.reset()
            self.assertEqual(await self._call(middleware), 204)


if __name__ == "__main__":
    unittest.main()
