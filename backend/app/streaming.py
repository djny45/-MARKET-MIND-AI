"""Low-overhead in-process async event primitives with bounded latency telemetry.

This is an in-process, non-durable queue. Metrics describe queue handoff latency,
not network, persistence, model-inference, or end-to-end research latency.
"""
import asyncio
import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class MarketEvent:
    channel: str
    payload: dict
    created_ns: int = field(default_factory=time.perf_counter_ns)


class EventBus:
    def __init__(self, queue_size: int = 10000, latency_window: int = 4096):
        if queue_size < 1 or latency_window < 1:
            raise ValueError("queue_size and latency_window must be positive")
        self.queue = asyncio.Queue(maxsize=queue_size)
        self.dropped = 0
        self.published = 0
        self.consumed = 0
        self.high_watermark = 0
        self._queue_latency_ns = deque(maxlen=latency_window)

    async def publish(self, event: MarketEvent):
        """Non-blocking enqueue; overload is explicit via the dropped counter."""
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            self.dropped += 1
            return False
        self.published += 1
        self.high_watermark = max(self.high_watermark, self.queue.qsize())
        return True

    async def consume(self):
        while True:
            event = await self.queue.get()
            try:
                self.consumed += 1
                self._queue_latency_ns.append(max(0, time.perf_counter_ns() - event.created_ns))
                yield event
            finally:
                self.queue.task_done()

    @staticmethod
    def _percentile_us(samples, percentile):
        if not samples:
            return None
        ordered = sorted(samples)
        index = max(0, min(len(ordered) - 1, int((percentile / 100) * len(ordered) + 0.999999) - 1))
        return round(ordered[index] / 1000, 3)

    def metrics(self):
        samples = tuple(self._queue_latency_ns)
        return {
            "queue_depth": self.queue.qsize(),
            "queue_capacity": self.queue.maxsize,
            "queue_high_watermark": self.high_watermark,
            "published_events": self.published,
            "consumed_events": self.consumed,
            "dropped_events": self.dropped,
            "queue_latency_us": {
                "sample_count": len(samples),
                "p50": self._percentile_us(samples, 50),
                "p95": self._percentile_us(samples, 95),
                "p99": self._percentile_us(samples, 99),
            },
            "clock": "process_monotonic",
            "durability": "in_memory_only",
        }


def latency_budget():
    return {
        "microsecond_end_to_end_guarantee": False,
        "scope": "In-process queue handoff is measured in microseconds; end-to-end latency depends on compute, I/O, providers, and hardware.",
        "optimizations": [
            "non-blocking bounded in-memory queue",
            "async network I/O",
            "explicit backpressure and dropped-event counters",
            "persistent connections when permitted",
            "batching and vectorized analytics",
            "monotonic stage timestamps",
            "separate ingestion, compute, persistence and UI workloads",
        ],
        "measure": ["p50", "p95", "p99", "queue depth", "high-water mark", "dropped events"],
        "execution": "Research only; no broker order routing.",
    }
