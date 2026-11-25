"""Tests for the paper-trading subsystem (engine, store, reports, config)."""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.paper_trading.config import VirtualCapitalConfig
from app.paper_trading.engine import VirtualBroker
from app.paper_trading.reports import daily_report, monthly_report, portfolio_summary, rank_agents
from app.paper_trading.store import PaperTradeStore


class PaperConfigTests(unittest.TestCase):
    def test_defaults_validate(self):
        cfg = VirtualCapitalConfig()
        self.assertEqual(cfg.registered_agents, 550)
        self.assertEqual(cfg.initial_capital_per_agent, 500.0)
        self.assertEqual(cfg.total_virtual_capital, 275000.0)

    def test_total_is_agents_times_capital(self):
        cfg = VirtualCapitalConfig(registered_agents=10, total_virtual_capital=5000.0)
        self.assertEqual(cfg.total_virtual_capital, cfg.registered_agents * cfg.initial_capital_per_agent)


class PaperStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Path(self._tmp.name) / "paper_trading.db"
        self.store = PaperTradeStore(VirtualCapitalConfig())
        self.store.config.db_filename = "paper_trading.db"
        # Redirect DB path to the temp dir for this test.
        self.store._path = str(self.db)
        self.store.init_schema()

    def tearDown(self):
        self._tmp.cleanup()

    def test_upsert_portfolio_and_read(self):
        self.store.upsert_portfolio("agent_0001", 500.0)
        pf = self.store.portfolio("agent_0001")
        self.assertEqual(pf["current_cash"], 500.0)
        self.assertEqual(pf["status"], "initialized")

    def test_idempotent_init(self):
        self.store.upsert_portfolio("agent_0001", 500.0)
        self.store.upsert_portfolio("agent_0001", 999.0)
        self.assertEqual(self.store.portfolio("agent_0001")["current_cash"], 500.0)


class VirtualBrokerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        db = Path(self._tmp.name) / "paper_trading.db"
        cfg = VirtualCapitalConfig(registered_agents=5, initial_capital_per_agent=1000.0, total_virtual_capital=5000.0)
        self.store = PaperTradeStore(cfg)
        self.store._path = str(db)
        self.store.init_schema()
        self.broker = VirtualBroker(config=cfg, store=self.store)

    def tearDown(self):
        self._tmp.cleanup()

    def test_initializes_five_portfolios(self):
        n = self.broker.initialize_all_portfolios()
        self.assertEqual(n, 5)
        for i in range(1, 6):
            pf = self.store.portfolio(f"agent_{i:04d}")
            self.assertIsNotNone(pf)
            self.assertEqual(pf["current_cash"], 1000.0)

    def test_buy_updates_cash_and_positions(self):
        self.broker.initialize_all_portfolios()
        trade = self.broker.place_order("agent_0001", "AAPL", 2, "BUY", price=100.0)
        self.assertTrue(trade["ok"] if isinstance(trade, dict) and "ok" in trade else True)
        pf = self.broker.portfolio("agent_0001")
        self.assertGreater(pf.portfolio_value, 0)
        pos = self.store.get_position("agent_0001", "AAPL")
        self.assertEqual(pos["quantity"], 2)
        self.assertGreaterEqual(pos["avg_entry"], 0)

    def test_sell_records_realized_pnl(self):
        self.broker.initialize_all_portfolios()
        self.broker.place_order("agent_0001", "AAPL", 2, "BUY", price=100.0)
        trade = self.broker.place_order("agent_0001", "AAPL", 2, "SELL", price=120.0)
        self.assertGreater(trade["pnl"], 0)
        pf = self.broker.portfolio("agent_0001")
        self.assertGreater(pf.realized_pnl, 0)
        self.assertFalse(self.store.get_position("agent_0001", "AAPL"))

    def test_portfolio_summary_counts(self):
        self.broker.initialize_all_portfolios()
        summary = portfolio_summary(self.store)
        self.assertEqual(summary["registered_agents"], 5)
        self.assertEqual(summary["initialized_portfolios"], 5)
        self.assertGreaterEqual(summary["total_virtual_capital"], 5000.0)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = PaperTradeStore(VirtualCapitalConfig(registered_agents=3, total_virtual_capital=1500.0))
        self.store._path = str(Path(self._tmp.name) / "paper_trading.db")
        self.store.init_schema()

    def tearDown(self):
        self._tmp.cleanup()

    def test_daily_report_and_rankings_computed(self):
        for i in range(1, 4):
            aid = f"agent_{i:04d}"
            self.store.upsert_portfolio(aid, 500.0)
            self.store.append_trade(aid, "AAPL", "SELL", 5, 100.0, 0, 0, 50.0 * i, True, "2026-01-02T10:00:00")
        rows = daily_report(self.store, "2026-01-02")
        self.assertTrue(rows)
        self.assertEqual(len(rows), 3)
        ranked = rank_agents(self.store, "test-period")
        self.assertEqual(len(ranked), 3)
        self.assertEqual(ranked[0]["rank"], 1)


if __name__ == "__main__":
    unittest.main()
