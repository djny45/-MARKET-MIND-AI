import unittest
from email.message import Message
from unittest.mock import patch

from app import browser_research as br


class FakeResponse:
    def __init__(self, body: bytes, content_type: str = "text/html") -> None:
        self.body = body
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.body[:size]


class BrowserResearchPolicyTests(unittest.TestCase):
    def test_https_and_allowlisted_host_required(self):
        invalid = [
            "http://en.wikipedia.org/wiki/Test",
            "https://evil.example.com/x",
            "https://user:pass@en.wikipedia.org/",
            "https://en.wikipedia.org:8443/x",
            "x" * (br.MAX_URL_CHARS + 1),
        ]
        for url in invalid:
            with self.subTest(url=url[:40]):
                with self.assertRaises(br.URLPolicyError):
                    br.validate_url(url)

    def test_valid_url_is_normalized(self):
        url, host = br.validate_url("https://en.wikipedia.org/wiki/Test?utm=1#frag")
        self.assertEqual(host, "en.wikipedia.org")
        self.assertEqual(url, "https://en.wikipedia.org/wiki/Test")
        self.assertNotIn("utm", url)
        self.assertNotIn("#", url)

    def test_private_and_loopback_addresses_are_blocked(self):
        for address in ("127.0.0.1", "10.0.0.5", "169.254.169.254", "::1"):
            with self.subTest(address=address):
                info = [(2, 1, 6, "", (address, 443))]
                with patch.object(br.socket, "getaddrinfo", return_value=info):
                    with self.assertRaises(br.URLPolicyError):
                        br.assert_public_endpoint("en.wikipedia.org")

    def test_redirects_are_never_followed(self):
        with self.assertRaises(br.URLPolicyError):
            br._NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.example/")

    def test_policy_failures_return_structured_errors_without_network(self):
        with patch.object(br, "build_opener", side_effect=AssertionError("network used")):
            result = br.fetch_research_page("http://evil.example/")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "https_required")
        self.assertFalse(result["side_effects"])

    def test_script_and_style_content_is_stripped(self):
        html = "<html><head><style>x{}</style></head><body><script>alert(1)</script><p>Hello  world</p></body></html>"
        text = br.html_to_text(html)
        self.assertIn("Hello world", text)
        self.assertNotIn("alert", text)
        self.assertNotIn("x{}", text)

    def test_successful_fetch_is_plain_text_with_audit_metadata(self):
        response = FakeResponse(b"<html><body><p>Public research text.</p></body></html>")
        with patch.object(br, "build_opener") as opener:
            opener.return_value.open.return_value = response
            with patch.object(br, "assert_public_endpoint"):
                result = br.fetch_research_page("https://en.wikipedia.org/wiki/Test")
        self.assertTrue(result["ok"])
        self.assertIn("Public research text.", result["text"])
        self.assertFalse(result["javascript_executed"])
        self.assertFalse(result["credentials_used"])
        self.assertFalse(result["local_file_access"])
        self.assertFalse(result["side_effects"])
        self.assertTrue(result["research_only"])
        self.assertTrue(result["policy"]["private_network_blocked"])

    def test_text_is_truncated_to_bound(self):
        body = ("word " * 10_000).encode()
        with patch.object(br, "build_opener") as opener:
            opener.return_value.open.return_value = FakeResponse(body, "text/plain")
            with patch.object(br, "assert_public_endpoint"):
                result = br.fetch_research_page("https://en.wikipedia.org/wiki/Test")
        self.assertTrue(result["text_truncated"])
        self.assertLessEqual(len(result["text"]), br.MAX_TEXT_CHARS)


if __name__ == "__main__":
    unittest.main()
