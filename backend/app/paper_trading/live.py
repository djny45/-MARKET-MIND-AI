"""LivePaperTrader — continuous live-market paper trading.

Subscribes to stored market bars via market_store.get_bars (there is no live
exchange connection; paper trading simulates an exchange by reading stored
market observations in order), and executes virtual orders for each agent.
Runs as an asyncio task against the VirtualBroker; every trade is logged
through PaperTradeStore so reports and rankings are real.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..market_store import get_bars
from .config import VirtualCapitalConfig
from .engine import VirtualBroker

logger = logging.getLogger(__name__)

def paper_signal(symbol: str, bars: list[dict], lookback: int = 10) -> int:
    """Simple paper signal: long when close is above the trailing lookback mean."""
    closes = [float(b["close"]) for b in bars if b.get("close")]
    if len(closes) < lookback:
        return 0
    window = closes[-lookback:]
    mean = sum(window) / len(window)
    return 1 if closes[-1] < mean else 0


class LivePaperTrader:
    """Runs a background paper-trading loop; every iteration trades 1 agent."""

    def __init__(self, broker: VirtualBroker, config: VirtualCapitalConfig | None = None):
        self.broker = broker
        self.config = config or VirtualCapitalConfig.from_env()
        self._task: asyncio.Task | None = None
        self.last_executed_at = 0.0
        self.agent_cursor = 0

    # -- lifecycle ------------------------------------------------------------
    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> "LivePaperTrader":
        if self.is_running or not self.config.enabled:
            return self
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._run())
        return self

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # never crash the app
                logger.exception("paper-trading tick failed: %s", exc)
            # Sleep with wakeups capped so cancellation stays responsive.
            try:
                await asyncio.sleep(max(1.0, self.config.interval_seconds))
            except asyncio.CancelledError:
                raise

    async def tick(self, symbol: str | None = None) -> list[dict]:
        """Run one cycle in a worker thread so the API event loop stays responsive."""
        return await asyncio.to_thread(self._tick_sync, symbol)

    def _tick_sync(self, symbol: str | None = None) -> list[dict]:
        """One paper-trading cycle: trade all configured symbols, then metrics.

        The whole cycle runs inside one store transaction: on NFS each commit
        costs ~40ms, so committing per order turned a tick into 8-32s of I/O.
        One commit keeps identical rows and final state.
        """
        with self.broker.store.transaction():
            return self._tick_body(symbol)

    def _tick_body(self, symbol: str | None = None) -> list[dict]:
        executed: list[dict] = []
        symbols = [symbol] if symbol else list(self.config.symbols)
        for sym in symbols:
            try:
                data = get_bars(sym, self.config.market_interval, limit=120)
            except Exception:
                data = {"bars": []}
            bars = data.get("bars", [])
            if not bars:
                # No stored bars yet: skip this symbol rather than invent prices.
                continue
            price = float(bars[-1]["close"])
            sig = paper_signal(sym, bars)
            # Every registered agent participates in live paper trading on
            # every tick. Sizing is fractional so $500 portfolios can hold
            # high-priced instruments such as BTC.
            all_ids = [p["agent_id"] for p in self.broker.store.portfolios()]
            size = max(1, self.config.agents_per_tick)
            start = self.agent_cursor % len(all_ids) if all_ids else 0
            agent_ids = [all_ids[(start + i) % len(all_ids)] for i in range(min(size, len(all_ids)))] if all_ids else []
            self.agent_cursor = (start + len(agent_ids)) % (len(all_ids) or 1)
            # Bulk-load state for this symbol: one query each instead of
            # ~2 per agent (NFS round trips dominated the tick).
            open_for_symbol = self.broker.store.positions_for_symbol(sym)
            cash = self.broker.store.cash_by_agent()
            for agent_id in agent_ids:
                try:
                    existing = open_for_symbol.get(agent_id)
                    pos_side = int(existing["quantity"]) if existing else 0
                    want = 1 if sig > 0 else 0
                    if want and pos_side == 0:
                        agent_cash = cash.get(agent_id)
                        if agent_cash is None:
                            continue
                        qty = round((agent_cash * 0.1) / max(price, 0.01), 6)
                        if qty <= 0 or agent_cash < (qty * price) * 1.001:
                            continue  # can't afford this tick; skip without error spam
                        trade = self.broker.place_order(
                            agent_id, sym, qty, "BUY", price=price,
                            stop_loss_pct=self.config.stop_loss_pct,
                            take_profit_pct=self.config.take_profit_pct,
                            note=f"live_signal={sig}")
                        executed.append(trade)
                        cash[agent_id] = agent_cash - qty * price
                    # Simulated exits: close positions whose stop/target is hit.
                    for closed in self.broker.check_stop_loss_take_profit(
                            agent_id, sym, price):
                        executed.append(closed)
                except Exception:
                    logger.exception("trade failed for %s/%s", agent_id, sym)
            # Re-price every open position in this symbol, not only the slice
            # that traded, so all 550 portfolios stay on the live mark.
            try:
                self.broker.mark_symbol_to_market(sym, price)
            except Exception:
                logger.exception("mark-to-market failed for %s", sym)
        try:
            self.broker.refresh_all_metrics()
        except Exception:
            pass
        import time
        self.last_executed_at = time.time()
        return executed
