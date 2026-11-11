import unittest

from app.security_config import parse_frontend_origins


class FrontendOriginConfigTests(unittest.TestCase):
    def test_accepts_explicit_http_and_https_origins(self):
        self.assertEqual(
            parse_frontend_origins(
                "http://localhost:5173, https://market.example.com/"
            ),
            ["http://localhost:5173", "https://market.example.com"],
        )

    def test_normalizes_case_and_deduplicates_origins(self):
        self.assertEqual(
            parse_frontend_origins(
                "HTTPS://MARKET.EXAMPLE.COM,https://market.example.com/"
            ),
            ["https://market.example.com"],
        )

    def test_normalizes_default_ports_to_browser_origin_form(self):
        self.assertEqual(
            parse_frontend_origins(
                "https://market.example.com:443,http://localhost:80"
            ),
            ["https://market.example.com", "http://localhost"],
        )

    def test_accepts_ipv6_loopback_origin(self):
        self.assertEqual(
            parse_frontend_origins("http://[::1]:5173"),
            ["http://[::1]:5173"],
        )

    def test_rejects_wildcard_origins(self):
        for value in ("*", "https://*", "http://localhost:5173,*"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "wildcard"):
                    parse_frontend_origins(value)

    def test_rejects_non_origin_url_components(self):
        invalid = (
            "ftp://market.example.com",
            "https://market.example.com/app",
            "https://user:password@market.example.com",
            "https://market.example.com?debug=1",
            "https://market.example.com#fragment",
            "https://market.example.com:bad",
            "https://market.example.com:",
            "https://market example.com",
        )
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_frontend_origins(value)

    def test_rejects_empty_allowlist(self):
        for value in ("", " ,  "):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "at least one"):
                    parse_frontend_origins(value)


if __name__ == "__main__":
    unittest.main()
