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

    def test_news_social_merge_preserves_sources_and_marks_claims_unverified(self):
        response = self.client.post("/api/research/evidence/merge", json={
            "news_items": [{
                "source": "SEC", "title": "Official filing", "url": "https://sec.gov/filing",
                "published_at": "2026-11-01T10:00:00Z",
            }],
            "social_items": [{
                "source": "reddit-demo", "title": "Community claim",
                "url": "https://reddit.com/r/demo/post",
                "published_at": "2026-11-01T11:00:00Z",
            }],
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["schema"], "market_mind_evidence_v1")
        self.assertEqual(body["count"], 2)
        self.assertEqual(set(body["channels"]), {"news", "social"})
        self.assertTrue(all(item["claim_status"] == "unverified" for item in body["items"]))
        self.assertEqual({item["source"] for item in body["items"]}, {"SEC", "reddit-demo"})
        self.assertEqual(body["coverage"], "only_configured_sources")

    def test_news_social_merge_deduplicates_same_source_url(self):
        response = self.client.post("/api/research/evidence/merge", json={
            "news_items": [{"source": "publisher", "title": "Same", "url": "https://example.com/a"}],
            "social_items": [{"source": "Publisher", "title": "Duplicate", "url": "https://example.com/a"}],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)


    def test_social_synthesis_uses_shared_core_and_keeps_execution_disabled(self):
        evidence = {
            "items": [{"title": "unverified discussion", "url": "https://reddit.com/r/demo/1"}],
            "sources_checked": 1,
            "sources_ok": 1,
            "source_results": [],
            "coverage": "configured_public_feeds_only",
            "execution": "disabled",
            "mode": "public_social_research",
            "financial_advice": False,
        }
        synthesis = {"status": "not_configured", "summary": None}
        with patch("app.main.social_sources.ingest_public_social_feeds",
                   new_callable=AsyncMock, return_value=evidence), \\
             patch("app.main.synthesize_research", return_value=synthesis) as synth:
            response = self.client.post("/api/research/social-feeds/synthesize", json={
                "feeds": [{
                    "source": "reddit-demo",
                    "feed_url": "https://www.reddit.com/r/demo/.rss",
                }]
            })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["evidence"]["coverage"], "configured_public_feeds_only")
        self.assertEqual(body["synthesis"], synthesis)
        self.assertEqual(body["execution"], "disabled")
        self.assertFalse(body["financial_advice"])
        synth.assert_called_once()
        core_input = synth.call_args.args[0]
        self.assertEqual(core_input["research_type"], "public_social_discussion")
        self.assertIn("unverified claims", core_input["agent_context"])

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
