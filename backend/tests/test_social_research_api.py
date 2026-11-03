import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app


class SocialResearchApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_rejects_non_reddit_or_non_https_feed_urls(self):
        for url in (
            "http://www.reddit.com/r/test/.rss",
            "https://example.com/feed.rss",
            "https://www.reddit.com/private",
            "https://user:pass@www.reddit.com/r/test/.rss",
            "https://www.reddit.com:badport/r/test/.rss",
            "https://www.reddit.com/r/test/.rss?redirect=1",
            "https://www.reddit.com/r/test/.rss#fragment",
        ):
            with self.subTest(url=url):
                response = self.client.post("/api/research/social-feeds", json={
                    "feeds": [{"source": "test", "feed_url": url}]
                })
                self.assertEqual(response.status_code, 400)

    def test_endpoint_calls_adapter_and_returns_research_only_metadata(self):
        mocked = {
            "items": [{"title": "mock discussion", "url": "https://reddit.com/r/test/1"}],
            "sources_checked": 1,
            "sources_ok": 1,
            "source_results": [],
            "coverage": "configured_public_feeds_only",
            "execution": "disabled",
        }
        with patch("app.main.social_sources.ingest_public_social_feeds",
                   new_callable=AsyncMock, return_value=mocked) as ingest:
            response = self.client.post("/api/research/social-feeds", json={
                "feeds": [{
                    "source": "reddit-test",
                    "feed_url": "https://www.reddit.com/r/test/.rss",
                }]
            })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["mode"], "public_social_research")
        self.assertFalse(body["financial_advice"])
        self.assertEqual(body["execution"], "disabled")
        ingest.assert_awaited_once_with(
            {"reddit-test": "https://www.reddit.com/r/test/.rss"},
            concurrency=3,
        )


if __name__ == "__main__":
    unittest.main()
