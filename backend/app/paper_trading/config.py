"""Virtual capital configuration for the paper-trading subsystem.

Per the operator spec:
  - Registered agents: 550 (matches list_workers() / worker_*.py WORKERS)
  - Initial virtual capital per agent: $500 USD
  - Total virtual capital: $275,000 USD
  - Independent portfolios per agent (no sharing of balances).
  - All execution is virtual — broker_execution stays False permanently.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class VirtualCapitalConfig:
    """Capital and trading rules for the virtual-paper environment."""

    # -- identity -------------------------------------------------------------
    app_name: str = "MARKET-MIND-AI Paper Trading"
    platform_slug: str = "market-mind-paper"

    # -- capital ---------------------------------------------------------------
    registered_agents: int = 550
    initial_capital_per_agent: float = 500.00
    total_virtual_capital: float = 275_000.00  # 550 * 500, verified by default.

    # -- simulated costs ---------------------------------------------------------
    commission_bps: float = 0.50      # per-trade fee, basis points of notional
    slippage_bps: float = 0.25        # simulated slippage basis points of notional
    max_position_pct: float = 75.0    # max of portfolio per position

    # -- stop-loss / take-profit (simulated) ---------------------------------------
    stop_loss_pct: float | None = 5.0  # percent of entry; None = disabled
    take_profit_pct: float | None = 15.0

    # -- state location -------------------------------------------------------------
    db_filename: str = "paper_trading.db"

    # -- live trading loop ------------------------------------------------------------
    enabled: bool = True
    symbols: tuple[str, ...] = ("AAPL", "MSFT", "GOOG", "TSLA", "NVDA")
    interval_seconds: float = 60.0

    def __post_init__(self) -> None:
        if abs(self.registered_agents * self.initial_capital_per_agent
               - self.total_virtual_capital) > 0.01:
            raise ValueError(
                "registered_agents * initial_capital_per_agent must equal total_virtual_capital"
            )

    @classmethod
    def from_env(cls) -> "VirtualCapitalConfig":
        cfg = cls()
        if os.getenv("MM_PAPER_ENABLED", "").lower() in {"0", "false", "off"}:
            cfg.enabled = False
        return cfg

    def database_path(self) -> str:
        import pathlib
        main_db = os.getenv("MARKET_MIND_DB", "./data/market_mind.db")
        return str(pathlib.Path(main_db).with_name(self.db_filename))
