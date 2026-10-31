import unittest

from app.streaming import EventBus, MarketEvent


class EventBusTests(unittest.IsolatedAsyncioTestCase):
    async def test_publish_consume_and_latency_metrics(self):
        bus = EventBus(queue_size=4)
        event = MarketEvent("prices", {"symbol": "TEST"})
        self.assertTrue(await bus.publish(event))
        consumer = bus.consume()
        received = await anext(consumer)
        self.assertIs(received, event)
        metrics = bus.metrics()
        self.assertEqual(metrics["published_events"], 1)
        self.assertEqual(metrics["consumed_events"], 1)
        self.assertEqual(metrics["dropped_events"], 0)
        self.assertEqual(metrics["queue_depth"], 0)
        self.assertEqual(metrics["queue_latency_us"]["sample_count"], 1)
        self.assertIsNotNone(metrics["queue_latency_us"]["p50"])
        await consumer.aclose()

    async def test_full_queue_drops_without_blocking(self):
        bus = EventBus(queue_size=1)
        self.assertTrue(await bus.publish(MarketEvent("prices", {"n": 1})))
        self.assertFalse(await bus.publish(MarketEvent("prices", {"n": 2})))
        metrics = bus.metrics()
        self.assertEqual(metrics["queue_depth"], 1)
        self.assertEqual(metrics["queue_high_watermark"], 1)
        self.assertEqual(metrics["dropped_events"], 1)
        consumer = bus.consume()
        await anext(consumer)
        await consumer.aclose()

    def test_invalid_capacity_rejected(self):
        with self.assertRaises(ValueError):
            EventBus(queue_size=0)


if __name__ == "__main__":
    unittest.main()
