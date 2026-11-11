import asyncio
import unittest
from unittest.mock import patch

from app import social_sources


RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
<item><title>Discussion headline</title><link>https://example.org/post/1</link>
<pubDate>Mon, 02 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title>Missing link</title></item>
</channel></rss>"""


class SocialSourceTests(unittest.TestCase):
    def test_parse_rss_preserves_provenance_and_omits_invalid_item(self):
        items = social_sources.parse_rss(RSS, "sample-feed", "https://example.org/rss")
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["source"], "sample-feed")
        self.assertEqual(item["url"], "https://example.org/post/1")
        self.assertEqual(item["content_policy"], "title_link_metadata_only")
        self.assertIsNotNone(item["published_at"])

    def test_feed_error_is_reported_as_status_not_raised(self):
        mock_opener = unittest.mock.Mock()
        mock_opener.open.side_effect = OSError("offline")
        with patch("app.social_sources.build_opener", return_value=mock_opener):
            result = asyncio.run(
                social_sources.fetch_public_rss("sample", "https://example.org/rss")
            )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["error"], "Feed fetch failed")
        self.assertEqual(result["error_type"], "OSError")
        self.assertNotIn("offline", result["error"])

    def test_configured_feed_ingestion_deduplicates_items(self):
        async def fake_fetch(source, url):
            return {
                "source": source, "feed_url": url, "status": "ok",
                "count": 1,
                "items": [{"id": "same-id", "source": source, "url": url}],
            }

        with patch("app.social_sources.fetch_public_rss", side_effect=fake_fetch):
            result = asyncio.run(social_sources.ingest_public_social_feeds({
                "feed-a": "https://a.example/rss",
                "feed-b": "https://b.example/rss",
            }))
        self.assertEqual(result["sources_checked"], 2)
        self.assertEqual(result["sources_ok"], 2)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["coverage"], "configured_public_feeds_only")
        self.assertEqual(result["execution"], "disabled")


if __name__ == "__main__":
    unittest.main()
