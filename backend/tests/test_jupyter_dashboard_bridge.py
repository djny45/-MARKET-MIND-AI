"""Tests for the Jupyter dashboard bridge (no network, no credentials)."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1].parent / "scripts"))

import jupyter_dashboard_bridge as bridge  # noqa: E402


class FakeClient:
    """Returns deterministic API payloads; no login or real requests."""

    def __init__(self, status=None, portfolios=None, overview=None):
        self.payloads = {
            "/api/paper/status": (200, status or {
                "registered_agents": 550, "agents_with_open_positions": 2,
                "total_virtual_capital": 275000.0, "total_portfolio_value": 275000.0,
            }),
            "/api/paper/portfolios": (200, portfolios or {"portfolios": [
                {"agent_id": "agent_0001", "realized_pnl": 10.0, "max_drawdown": 0.01,
                 "positions": [{"symbol": "AAPL", "quantity": 2}]},
            ]}),
            "/api/market-data/overview": (200, overview or {"bars": []}),
        }

    def request(self, method, path, body=None):
        if path.startswith("/api/paper/trades?"):
            return (200, {"trades": [
                {"agent_id": "agent_0001", "symbol": "AAPL", "side": "BUY",
                 "quantity": 1, "price": 100.0, "pnl": 0, "executed_at": "2026-01-01T00:00:00Z"}
            ]})
        return self.payloads[path]


class BridgeTests(unittest.TestCase):
    def test_snapshot_uses_backend_values(self):
        snap = bridge.build_snapshot(FakeClient())
        self.assertEqual(snap["pnl"]["registered_agents"], 550)
        self.assertEqual(snap["pnl"]["total_virtual_capital"], 275000.0)
        self.assertEqual(snap["pnl"]["realized_pnl"], 10.0)
        self.assertEqual(snap["broker_execution"], False)
        self.assertEqual(len(snap["open_positions"]), 1)

    def test_no_live_prices_without_feed(self):
        snap = bridge.build_snapshot(FakeClient())
        self.assertEqual(snap["market_data_status"], "unavailable")
        self.assertEqual(snap["market_prices"], [])

    def test_prices_published_only_with_real_observations(self):
        bars = [{"symbol": "AAPL", "close": 101.5, "source": "stored", "status": "ok",
                 "timestamp": "2026-01-01T00:00:00Z"}]
        snap = bridge.build_snapshot(FakeClient(overview={"bars": bars}))
        self.assertEqual(snap["market_data_status"], "available")
        self.assertEqual(snap["market_prices"][0]["symbol"], "AAPL")


if __name__ == "__main__":
    unittest.main()
