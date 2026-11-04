"""Run the offline webhook payload validation lab.

From the repository root:
    python backend/examples/webhook_payload_lab_demo.py

This is a local parser demonstration only. It does not open a port, receive
webhooks, forward notifications, connect to TradingView, or trade.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.webhook_payload_lab import validate_payload  # noqa: E402


def main() -> int:
    sample = {
        "event_id": "offline-demo-001",
        "source": "synthetic",
        "symbol": "EXAMPLE",
        "timeframe": "1D",
        "message": "Fabricated sample event for parser testing",
        "created_at": "2025-01-01T00:00:00Z",
    }
    event = validate_payload(sample)
    print("OFFLINE WEBHOOK PAYLOAD LAB — SYNTHETIC EVENT")
    print(f"Validated event ID: {event['event_id']}")
    print(f"Source: {event['source']}")
    print(f"Message: {event['message']}")
    print("No HTTP listener, external notifications, or trading actions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
