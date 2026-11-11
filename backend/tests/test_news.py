import asyncio
import unittest
from unittest.mock import patch

from app import news


class NewsFeedErrorHandlingTests(unittest.TestCase):
    def test_feed_failure_redacts_transport_details(self):
        async def fail_fetch(source, url):
            raise OSError("connection to 10.0.0.8:8080 failed")

        with patch("app.news.fetch_feed", side_effect=fail_fetch):
            result = asyncio.run(news.ingest_news({
                "test-feed": "https://example.org/rss"
            }))

        self.assertEqual(result["sources"], 1)
        self.assertEqual(result["count"], 1)
        item = result["items"][0]
        self.assertEqual(item["error"], "Feed fetch failed")
        self.assertEqual(item["error_type"], "OSError")
        self.assertNotIn("10.0.0.8", str(item))


if __name__ == "__main__":
    unittest.main()
