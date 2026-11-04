"""Tests for the local-only inert webhook payload validator."""
import unittest

from app.webhook_payload_lab import validate_payload


class WebhookPayloadLabTests(unittest.TestCase):
    def test_accepts_sample_event(self):
        event = validate_payload(
            '{"event_id":"demo-001","source":"synthetic","message":"Example alert"}'
        )
        self.assertEqual(event["event_id"], "demo-001")
        self.assertEqual(event["source"], "synthetic")

    def test_rejects_live_source(self):
        with self.assertRaisesRegex(ValueError, "Only sample"):
            validate_payload(
                {"event_id": "x", "source": "tradingview", "message": "sample"}
            )

    def test_rejects_unknown_fields_including_secret(self):
        with self.assertRaisesRegex(ValueError, "Unsupported payload fields"):
            validate_payload(
                {"event_id": "x", "source": "sample", "message": "hi", "key": "secret"}
            )

    def test_rejects_missing_required_field(self):
        with self.assertRaisesRegex(ValueError, "Missing required"):
            validate_payload({"event_id": "x", "source": "sample"})

    def test_rejects_non_string_values(self):
        with self.assertRaisesRegex(ValueError, "must be a string"):
            validate_payload(
                {"event_id": "x", "source": "sample", "message": 123}
            )

    def test_rejects_invalid_json(self):
        with self.assertRaisesRegex(ValueError, "valid JSON"):
            validate_payload("{broken")

    def test_rejects_non_object_json(self):
        with self.assertRaisesRegex(ValueError, "JSON object"):
            validate_payload('["not", "an", "object"]')

    def test_rejects_invalid_utf8_bytes(self):
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            validate_payload(b"\xff")

    def test_trims_string_fields(self):
        event = validate_payload(
            {"event_id": "  id-1  ", "source": " sample ", "message": "  hello  "}
        )
        self.assertEqual(event["event_id"], "id-1")
        self.assertEqual(event["message"], "hello")

    def test_rejects_empty_string(self):
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            validate_payload({"event_id": "x", "source": "sample", "message": "  "})

    def test_rejects_oversized_payload(self):
        with self.assertRaisesRegex(ValueError, "maximum size"):
            validate_payload(" " * 8193)


if __name__ == "__main__":
    unittest.main()
