import os
import unittest
from unittest.mock import patch

from app.distributed_rate_limit import (
    INCREMENT_AND_EXPIRE_LUA,
    DistributedRateLimiter,
    DistributedRateLimitMiddleware,
    client_key,
)


class FakeRedis:
    def __init__(self, values=None, error=None):
        self.values = list(values or [])
        self.error = error
        self.calls = []

    def eval(self, script, keys_count, key, window):
        self.calls.append((script, keys_count, key, window))
        if self.error:
            raise self.error
        if self.values:
            return self.values.pop(0)
        return 1


class _Harness:
    def __init__(self, middleware):
        self.middleware = middleware
        self.status = None
        self.headers = {}

    async def __call__(self, scope, receive, send):
        await self.middleware(scope, receive, send)

    async def app(self, scope, receive, send):
        self.status = 204
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def request(self, path="/api/research/chart", method="GET", client=("127.0.0.1", 1234), headers=()):
        self.status = None

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            if message["type"] == "http.response.start":
                self.status = message["status"]
                self.headers = dict(message.get("headers", []))

        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
            "query_string": b"", "headers": list(headers), "server": ("test", 80),
            "client": client,
        }
        self.middleware.app = self.app
        await self.middleware(scope, receive, send)
        return self.status


class DistributedLimiterTests(unittest.IsolatedAsyncioTestCase):
    async def test_in_process_fallback_enforces_limit_without_redis(self):
        limiter = DistributedRateLimiter(limit=2)
        self.assertEqual(limiter.backend, "in-process")
        self.assertTrue(limiter.check("client-a").allowed)
        self.assertTrue(limiter.check("client-a").allowed)
        denied = limiter.check("client-a")
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.backend, "in-process")
        self.assertTrue(limiter.check("client-b").allowed)
        limiter.reset()
        self.assertTrue(limiter.check("client-a").allowed)

    async def test_redis_backend_uses_atomic_lua_increment(self):
        fake = FakeRedis(values=[1, 2, 3])
        limiter = DistributedRateLimiter(client=fake, limit=2)
        self.assertEqual(limiter.backend, "redis")
        self.assertTrue(limiter.check("client-a").allowed)
        self.assertTrue(limiter.check("client-a").allowed)
        self.assertFalse(limiter.check("client-a").allowed)
        self.assertEqual(len(fake.calls), 3)
        for script, keys_count, key, window in fake.calls:
            self.assertEqual(script, INCREMENT_AND_EXPIRE_LUA)
            self.assertEqual(keys_count, 1)
            self.assertTrue(key.startswith("mm:rl:60:"))
            self.assertEqual(window, 60)

    async def test_redis_failure_degrades_to_local_limiter(self):
        fake = FakeRedis(error=ConnectionError("redis down"))
        limiter = DistributedRateLimiter(client=fake, limit=1)
        self.assertTrue(limiter.check("client-a").allowed)
        self.assertEqual(limiter.backend, "in-process")
        self.assertFalse(limiter.check("client-a").allowed)
        self.assertEqual(len(fake.calls), 1)  # no repeated failing calls

    async def test_redis_recovers_after_cooldown(self):
        fake = FakeRedis(error=ConnectionError("redis down"))
        limiter = DistributedRateLimiter(client=fake, limit=5)
        clock = [100.0]
        limiter._now = lambda: clock[0]
        limiter.check("client-a")
        self.assertEqual(limiter.backend, "in-process")
        self.assertEqual(len(fake.calls), 1)
        clock[0] += 2.0
        limiter.check("client-a")  # still inside cooldown: no probe
        self.assertEqual(len(fake.calls), 1)
        fake.error = None
        clock[0] += 4.0
        self.assertTrue(limiter.check("client-a").allowed)
        self.assertEqual(len(fake.calls), 2)
        self.assertEqual(limiter.backend, "redis")

    async def test_invalid_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            DistributedRateLimiter(limit=-1)
        with self.assertRaises(ValueError):
            DistributedRateLimiter(limit=1, window_seconds=0)

    async def test_client_key_respects_trusted_proxy_count(self):
        headers = [(b"x-forwarded-for", b"10.0.0.1, 203.0.113.7, 198.51.100.4")]
        self.assertEqual(client_key({"client": ("127.0.0.1", 1), "headers": headers}), "127.0.0.1")
        self.assertEqual(
            client_key({"client": ("127.0.0.1", 1), "headers": headers}, trusted_proxies=2),
            "203.0.113.7",
        )

    async def test_middleware_is_noop_without_redis_url(self):
        harness = _Harness(DistributedRateLimitMiddleware(None))
        with patch.dict(os.environ, {"REDIS_URL": "", "API_RATE_LIMIT_PER_MINUTE": "1"}, clear=False):
            self.assertEqual(await harness.request(), 204)
            self.assertEqual(await harness.request(), 204)

    async def test_middleware_enforces_limit_and_exempts_health(self):
        limiter = DistributedRateLimiter(limit=1)
        middleware = DistributedRateLimitMiddleware(None, limiter=limiter)
        harness = _Harness(middleware)
        with patch.dict(os.environ, {"API_RATE_LIMIT_PER_MINUTE": "1"}, clear=False):
            self.assertEqual(await harness.request(), 204)
            self.assertEqual(await harness.request(), 429)
            self.assertEqual(await harness.request("/api/health"), 204)
            self.assertEqual(await harness.request("/api/ready"), 204)
            self.assertEqual(await harness.request(method="OPTIONS"), 204)


if __name__ == "__main__":
    unittest.main()
