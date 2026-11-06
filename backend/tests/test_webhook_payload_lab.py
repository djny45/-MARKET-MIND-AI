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

    def test_accepts_valid_json_bytes(self):
        event = validate_payload(
            b'{"event_id":"bytes-1","source":"local","message":"bytes event"}'
        )
        self.assertEqual(event["event_id"], "bytes-1")

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


    def test_rejects_non_string_dict_keys_before_json_normalization(self):
        with self.assertRaisesRegex(ValueError, "keys must be strings"):
            validate_payload({1: "not-a-string-key", "source": "sample", "message": "hi"})

    def test_rejects_non_string_values(self):
        with self.assertRaisesRegex(ValueError, "must be a string"):
            validate_payload(
                {"event_id": "x", "source": "sample", "message": 123}
            )

    def test_rejects_invalid_json(self):
        with self.assertRaisesRegex(ValueError, "valid JSON"):
            validate_payload("{broken")


    def test_rejects_duplicate_json_keys(self):
        with self.assertRaisesRegex(ValueError, "duplicate keys"):
            validate_payload('{"event_id":"first","event_id":"second","source":"sample","message":"hi"}')

    def test_rejects_nonstandard_nan_json_constant(self):
        with self.assertRaisesRegex(ValueError, "non-finite constants"):
            validate_payload('{"event_id":"x","source":"sample","message":"hi","extra":NaN}')

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

    def test_rejects_oversized_string_payload(self):
        with self.assertRaisesRegex(ValueError, "maximum size"):
            validate_payload(" " * 8193)

    def test_rejects_oversized_dict_payload(self):
        with self.assertRaisesRegex(ValueError, "maximum size"):
            validate_payload({
                "event_id": "x",
                "source": "sample",
                "message": "a" * 9000,
            })


if __name__ == "__main__":
    unittest.main()
