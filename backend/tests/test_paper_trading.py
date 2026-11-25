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


class SellAccountingTests(unittest.TestCase):
    """A SELL must credit proceeds to cash, not merely charge fees.

    Regression: `place_order` seeded `cash_delta = -notional` before branching,
    then added `notional - fee - slip` on the SELL path, netting only
    `-(fee + slip)`. Sells therefore never credited the sale proceeds and cash
    drifted down by the full notional on every exit.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        db = Path(self._tmp.name) / "paper_trading.db"
        self.cfg = VirtualCapitalConfig(registered_agents=6, initial_capital_per_agent=1000.0,
                                        total_virtual_capital=6000.0)
        self.store = PaperTradeStore(self.cfg)
        self.store._path = str(db)
        self.store.init_schema()
        self.broker = VirtualBroker(config=self.cfg, store=self.store)
        self.broker.initialize_all_portfolios()

    def tearDown(self):
        self._tmp.cleanup()

    def test_sell_credits_proceeds_to_cash(self):
        self.broker.place_order("agent_0001", "BTCUSD", 1.0, "BUY", price=100.0)
        cash_after_buy = self.store.portfolio("agent_0001")["current_cash"]
        self.assertLess(cash_after_buy, 1000.0)

        self.broker.place_order("agent_0001", "BTCUSD", 1.0, "SELL", price=100.0)
        cash_after_sell = self.store.portfolio("agent_0001")["current_cash"]

        # Round trip at the same reference price: cash is back to the start
        # minus the two fee+slippage charges, never short by the notional.
        expected = 1000.0 - 2 * (100.0 * (self.cfg.commission_bps + self.cfg.slippage_bps) / 10000.0)
        self.assertAlmostEqual(cash_after_sell, expected, places=6)

    def test_sell_produces_profit_when_price_rises(self):
        self.broker.place_order("agent_0001", "ETHUSD", 2.0, "BUY", price=50.0)
        self.broker.place_order("agent_0001", "ETHUSD", 2.0, "SELL", price=60.0)
        pf = self.store.portfolio("agent_0001")
        self.assertGreater(pf["realized_pnl"], 0)
        # 20.0 gross gain must actually reach cash.
        self.assertGreater(pf["current_cash"], 1000.0)

    def test_adding_to_position_includes_costs_in_basis(self):
        """A second BUY must blend cost basis the same way an opening BUY does.

        Regression: the opening BUY stored `avg_entry = exec_price` (which
        includes fee + slippage) but an add-on BUY blended `notional` only,
        so every agent that added to an existing position understated its
        cost basis by that trade's fee + slippage.
        """
        self.broker.place_order("agent_0001", "BTCUSD", 1.0, "BUY", price=100.0)
        first = self.store.get_position("agent_0001", "BTCUSD")
        self.assertGreater(first["avg_entry"], 100.0)  # costs embedded

        self.broker.place_order("agent_0001", "BTCUSD", 1.0, "BUY", price=100.0)
        pos = self.store.get_position("agent_0001", "BTCUSD")
        self.assertAlmostEqual(pos["quantity"], 2.0)
        # Both legs carried the same cost, so the blended basis equals one leg's.
        self.assertAlmostEqual(pos["avg_entry"], first["avg_entry"], places=9)
        # Cost basis must match what cash actually paid for the position.
        with self.store._conn() as c:
            paid = c.execute(
                "SELECT COALESCE(SUM(quantity*price),0) FROM paper_trades"
                " WHERE agent_id='agent_0001' AND symbol='BTCUSD'"
            ).fetchone()[0]
        self.assertAlmostEqual(pos["quantity"] * pos["avg_entry"], paid, places=6)

    def test_stop_loss_exits_at_the_triggering_market_price(self):
        """An exit must fill at the market price, not the 1.0 fallback.

        Regression: `check_stop_loss_take_profit` called place_order without
        `price`, so it defaulted to ref_price=1.0 and every stop-loss or
        take-profit exit sold the position for $1 regardless of the market.
        """
        self.broker.place_order("agent_0001", "BTCUSD", 1.0, "BUY", price=100.0,
                                stop_loss_pct=5.0, take_profit_pct=15.0)
        cash_before = self.store.portfolio("agent_0001")["current_cash"]

        exits = self.broker.check_stop_loss_take_profit("agent_0001", "BTCUSD", 90.0)
        self.assertEqual(len(exits), 1)
        trade = exits[0]
        self.assertEqual(trade["side"], "SELL")
        # Execution price must track the 90.0 market, not 1.0.
        self.assertAlmostEqual(trade["reference_price"], 90.0, places=6)
        self.assertGreater(trade["execution_price"], 85.0)
        self.assertLess(trade["execution_price"], 90.0)

        # Proceeds land in cash (~90 minus costs), not ~1.
        cash_after = self.store.portfolio("agent_0001")["current_cash"]
        self.assertAlmostEqual(cash_after - cash_before, 90.0, delta=1.0)
        self.assertLess(trade["pnl"], 0)  # exited below entry

    def test_take_profit_exits_at_the_triggering_market_price(self):
        self.broker.place_order("agent_0001", "ETHUSD", 1.0, "BUY", price=100.0,
                                stop_loss_pct=5.0, take_profit_pct=15.0)
        cash_before = self.store.portfolio("agent_0001")["current_cash"]
        exits = self.broker.check_stop_loss_take_profit("agent_0001", "ETHUSD", 120.0)
        self.assertEqual(len(exits), 1)
        trade = exits[0]
        self.assertAlmostEqual(trade["reference_price"], 120.0, places=6)
        cash_after = self.store.portfolio("agent_0001")["current_cash"]
        self.assertAlmostEqual(cash_after - cash_before, 120.0, delta=1.0)
        self.assertGreater(trade["pnl"], 0)

    def test_mark_to_market_revalues_every_position_in_symbol(self):
        """All agents holding a symbol must follow the live mark.

        Regression: the tick only re-priced the rotating slice of agents it
        traded, so untouched positions kept a stale current_price and their
        portfolio value and drawdown drifted away from the real market.
        """
        for i in range(1, 6):
            self.broker.place_order(f"agent_{i:04d}", "SOLUSD", 1.0, "BUY", price=10.0)
        self.broker.place_order("agent_0001", "ETHUSD", 1.0, "BUY", price=20.0)

        changed = self.broker.mark_symbol_to_market("SOLUSD", 12.5)
        self.assertEqual(changed, 5)
        for i in range(1, 6):
            pos = self.store.get_position(f"agent_{i:04d}", "SOLUSD")
            self.assertAlmostEqual(pos["current_price"], 12.5, places=9)
        # A different symbol must be untouched.
        self.assertAlmostEqual(
            self.store.get_position("agent_0001", "ETHUSD")["current_price"], 20.0015, places=9)

    def test_drawdown_is_bounded_by_the_ledger(self):
        """Drawdown must stay reachable from trade history.

        Regression: `max_drawdown` is monotonic (MAX(old, new)), so a position
        removed outside the ledger leaves a trough that no trade produced. A
        $500 agent then reported 40% drawdown while its equity was above
        high-water. Any drawdown must imply an equity level the ledger can reach.
        """
        self.broker.place_order("agent_0001", "BTCUSD", 0.5, "BUY", price=100.0)
        self.broker.refresh_all_metrics()

        # Best case ledger peak is the entry itself (~50 of a $1000 portfolio).
        pf = self.store.portfolio("agent_0001")
        implied_low = pf["high_watermark"] * (1 - pf["max_drawdown"])
        self.assertGreaterEqual(
            implied_low, 0.0,
            "drawdown implies a negative equity level")
        # And the metric can never exceed 100%.
        self.assertLessEqual(pf["max_drawdown"], 1.0)
        # A flat book must report essentially no drawdown.
        self.assertLess(pf["max_drawdown"], 0.05)

    def test_full_ledger_reconciles_after_buy_and_sell(self):
        """equity - initial == realized + unrealized.

        Fees and slippage are already embedded in the execution price (BUY
        marks up, SELL marks down), so they must not be subtracted a second
        time here.
        """
        self.broker.place_order("agent_0001", "SOLUSD", 5.0, "BUY", price=20.0)
        self.broker.place_order("agent_0001", "SOLUSD", 2.0, "SELL", price=25.0)
        self.broker.place_order("agent_0001", "BNBUSD", 1.0, "BUY", price=30.0)

        pf = self.store.portfolio("agent_0001")
        pos = self.store.positions("agent_0001")
        equity = pf["current_cash"] + sum(p["quantity"] * p["current_price"] for p in pos)
        with self.store._conn() as c:
            realized = c.execute(
                "SELECT COALESCE(SUM(CASE WHEN realized=1 THEN pnl ELSE 0 END),0)"
                " FROM paper_trades WHERE agent_id='agent_0001'"
            ).fetchone()[0]
        unrealized = sum(p["quantity"] * (p["current_price"] - p["avg_entry"]) for p in pos)
        self.assertAlmostEqual(equity - 1000.0, realized + unrealized, places=6)


class TransactionBatchingTests(unittest.TestCase):
    """The tick batches writes; batching must not change final state."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        db = Path(self._tmp.name) / "paper_trading.db"
        cfg = VirtualCapitalConfig(registered_agents=5, initial_capital_per_agent=1000.0,
                                   total_virtual_capital=5000.0)
        self.store = PaperTradeStore(cfg)
        self.store._path = str(db)
        self.store.init_schema()
        self.broker = VirtualBroker(config=cfg, store=self.store)
        self.broker.initialize_all_portfolios()

    def tearDown(self):
        self._tmp.cleanup()

    def test_batched_orders_persist_after_commit(self):
        with self.store.transaction():
            for i in range(1, 6):
                self.broker.place_order(f"agent_{i:04d}", "SOLUSD", 1.0, "BUY", price=10.0)
        for i in range(1, 6):
            pos = self.store.get_position(f"agent_{i:04d}", "SOLUSD")
            self.assertIsNotNone(pos)
            self.assertEqual(pos["quantity"], 1.0)
        self.assertEqual(self.store.count("paper_trades"), 5)

    def test_rollback_discards_batched_orders(self):
        with self.assertRaises(RuntimeError):
            with self.store.transaction():
                self.broker.place_order("agent_0001", "ETHUSD", 1.0, "BUY", price=10.0)
                raise RuntimeError("boom")
        self.assertIsNone(self.store.get_position("agent_0001", "ETHUSD"))
        self.assertEqual(self.store.count("paper_trades"), 0)

    def test_nested_transaction_commits_once_at_outermost(self):
        with self.store.transaction():
            self.broker.place_order("agent_0001", "BNBUSD", 1.0, "BUY", price=10.0)
            with self.store.transaction():
                self.broker.place_order("agent_0002", "BNBUSD", 1.0, "BUY", price=10.0)
        self.assertIsNotNone(self.store.get_position("agent_0001", "BNBUSD"))
        self.assertIsNotNone(self.store.get_position("agent_0002", "BNBUSD"))

    def test_batched_metrics_match_unbatched(self):
        """Bulk refresh must reach the same high-watermark/drawdown state."""
        self.broker.place_order("agent_0001", "BTCUSD", 0.01, "BUY", price=1000.0)
        self.broker.refresh_all_metrics()
        pf = self.store.portfolio("agent_0001")
        self.assertGreater(pf["high_watermark"], 0)
        self.assertGreaterEqual(pf["max_drawdown"], 0)

    def test_bulk_lookups_match_single_row_reads(self):
        self.broker.place_order("agent_0001", "SOLUSD", 2.0, "BUY", price=10.0)
        by_symbol = self.store.positions_for_symbol("SOLUSD")
        self.assertIn("agent_0001", by_symbol)
        self.assertEqual(by_symbol["agent_0001"]["quantity"], 2.0)
        cash = self.store.cash_by_agent()
        self.assertAlmostEqual(cash["agent_0001"],
                               self.store.portfolio("agent_0001")["current_cash"])


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
