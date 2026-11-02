import unittest

from app.landing_page_builder import build_landing_page
from app.workers import list_workers


class LandingPageBuilderTests(unittest.TestCase):
    def setUp(self):
        self.worker_id = list_workers()[0]["id"]

    def test_builds_static_html_and_marks_preview_only(self):
        result = build_landing_page(self.worker_id, {
            "title": "A Research Product",
            "subtitle": "Clear, concise positioning",
            "description": "A landing page description",
            "theme": "blue",
            "sections": [{"heading": "Features", "body": "Evidence-first workflow"}],
            "cta_label": "Learn more",
            "cta_url": "https://example.com/product",
        })
        self.assertIn("<!doctype html>", result["html"])
        self.assertIn("Evidence-first workflow", result["html"])
        self.assertIn('rel="noopener noreferrer"', result["html"])
        self.assertFalse(result["published"])
        self.assertFalse(result["scripts_executed"])
        self.assertEqual(result["skill_used"], "stageshow")

    def test_escapes_untrusted_content_and_rejects_script_url(self):
        result = build_landing_page(self.worker_id, {
            "title": "<script>alert(1)</script>",
            "sections": [{"heading": "Safe", "body": "<img src=x onerror=alert(1)>"}],
        })
        self.assertNotIn("<script>alert(1)</script>", result["html"])
        self.assertIn("&lt;script&gt;", result["html"])
        with self.assertRaises(ValueError):
            build_landing_page(self.worker_id, {"title": "Bad URL", "cta_label": "Go", "cta_url": "javascript:alert(1)"})

    def test_limits_sections_and_rejects_unknown_worker(self):
        with self.assertRaises(ValueError):
            build_landing_page("unknown-agent", {"title": "No"})
        with self.assertRaises(ValueError):
            build_landing_page(self.worker_id, {"title": "Too many", "sections": [{}] * 13})

    def test_rejects_invalid_theme_and_non_http_links(self):
        with self.assertRaises(ValueError):
            build_landing_page(self.worker_id, {"title": "Theme", "theme": "neon"})
        with self.assertRaises(ValueError):
            build_landing_page(self.worker_id, {"title": "URL", "cta_label": "Open", "cta_url": "//example.com"})


if __name__ == "__main__":
    unittest.main()
