"""Paper-trading subsystem for MARKET-MIND-AI (research-only, private mode).

Virtual-capital paper trading for registered agents. This subsystem is the
only place where a user-configured virtual capital amount is defined; it
never touches broker execution or real money paths.

Modules:
  config      — VirtualCapitalConfig, the $500-per-agent/550-agent rules.
  store       — SQLite persistence for portfolios, positions, trades, reports.
  engine      — VirtualBroker: portfolio init, virtual order execution with
                simulated fees/slippage, stop-loss/take-profit bookkeeping.
  live        — LivePaperTrader: continuous live-market paper trading loop
                (streams real bars from the market store and executes virtual
                orders per agent).
  backtest    — Historical strategy backtesting on market bars.
  reports     — Daily/monthly performance reports and strategy rankings.
  api         — FastAPI route handlers mounted by app.main.
"""
from .config import VirtualCapitalConfig
from .engine import VirtualBroker
from .store import PaperTradeStore

__all__ = ["VirtualCapitalConfig", "VirtualBroker", "PaperTradeStore"]
