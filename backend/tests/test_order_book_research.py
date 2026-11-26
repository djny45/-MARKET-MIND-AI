import unittest

from app.order_book_research import book_metrics, reconstruct_order_book


def snapshot(sequence=10):
    return {
        "event_type": "order_book_snapshot",
        "sequence_number": sequence,
        "payload": {
            "bids": [{"price": 100, "quantity": 2}, {"price": 99, "quantity": 3}],
            "asks": [{"price": 101, "quantity": 1}, {"price": 102, "quantity": 4}],
        },
    }


class OrderBookResearchTests(unittest.TestCase):
    def test_snapshot_reconstructs_sorted_book_and_metrics(self):
        result = reconstruct_order_book([snapshot()])
        self.assertTrue(result["valid"])
        self.assertEqual(result["bids"][0]["price"], 100)
        self.assertEqual(result["asks"][0]["price"], 101)
        self.assertEqual(result["metrics"]["spread"], 1)
        self.assertAlmostEqual(result["metrics"]["depth_imbalance"], (200 + 297 - 101 - 408) / (200 + 297 + 101 + 408))

    def test_delta_updates_and_deletes_levels(self):
        delta = {
            "event_type": "order_book_delta",
            "previous_sequence_number": 10,
            "sequence_number": 11,
            "payload": {
                "bids": [{"price": 100, "quantity": 0}, {"price": 98, "quantity": 5}],
                "asks": [{"price": 101, "quantity": 2}],
            },
        }
        result = reconstruct_order_book([snapshot(), delta])
        self.assertTrue(result["valid"])
        self.assertEqual([level["price"] for level in result["bids"]], [99, 98])
        self.assertEqual(result["asks"][0]["quantity"], 2)
        self.assertEqual(result["last_sequence_number"], 11)

    def test_sequence_gap_invalidates_book_until_new_snapshot(self):
        gap = {
            "event_type": "order_book_delta",
            "previous_sequence_number": 9,
            "sequence_number": 12,
            "payload": {"bids": [], "asks": []},
        }
        result = reconstruct_order_book([snapshot(), gap])
        self.assertFalse(result["valid"])
        self.assertEqual(result["bids"], [])
        self.assertIsNone(result["metrics"])
        self.assertEqual(result["sequence_gaps"][0]["reason"], "sequence_gap")

    def test_new_snapshot_recovers_after_gap(self):
        gap = {
            "event_type": "order_book_delta",
            "previous_sequence_number": 9,
            "sequence_number": 12,
            "payload": {"bids": [], "asks": []},
        }
        result = reconstruct_order_book([snapshot(), gap, snapshot(20)])
        self.assertTrue(result["valid"])
        self.assertEqual(result["last_sequence_number"], 20)
        self.assertEqual(len(result["sequence_gaps"]), 1)

    def test_rejects_crossed_book(self):
        invalid = {
            "event_type": "order_book_snapshot", "sequence_number": 1,
            "payload": {"bids": [{"price": 101, "quantity": 1}], "asks": [{"price": 100, "quantity": 1}]},
        }
        with self.assertRaisesRegex(ValueError, "crossed or locked"):
            reconstruct_order_book([invalid])

    def test_rejects_invalid_depth_band(self):
        with self.assertRaises(ValueError):
            book_metrics({100: 1}, {101: 1}, 0)

    def test_delta_before_snapshot_is_not_reported_as_a_valid_book(self):
        delta = {
            "event_type": "order_book_delta", "sequence_number": 1,
            "previous_sequence_number": 0, "payload": {"bids": [], "asks": []},
        }
        result = reconstruct_order_book([delta])
        self.assertFalse(result["valid"])
        self.assertEqual(result["sequence_gaps"][0]["reason"], "delta_without_valid_snapshot")


if __name__ == "__main__":
    unittest.main()
