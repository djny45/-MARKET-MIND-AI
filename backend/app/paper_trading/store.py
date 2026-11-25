"""SQLite persistence for the paper-trading subsystem.

Tables:
  paper_portfolios   — one row per agent: virtual cash, realized/unrealized P&L,
                       max_drawdown, created_at, status.
  paper_positions    — open virtual positions per agent/symbol.
  paper_trades       — every executed (virtual) trade with fees, slippage, pnl.
  paper_snapshots    — daily portfolio value/P&L snapshots for reporting.
  paper_rankings     — computed performance rankings per period.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Any

from ..sqlite_tuning import connect


def _db_path(config) -> str:
    return config.database_path()


class PaperTradeStore:
    """Thread-safe SQLite accessor for paper-trading records."""

    _INIT_LOCK = threading.Lock()

    def __init__(self, config) -> None:
        self.config = config
        self._path = _db_path(config)
        self._local = threading.local()

    def _conn(self) -> sqlite3.Connection:
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
            conn = connect(self._path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return conn

    def init_schema(self) -> None:
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS paper_portfolios (
                agent_id       TEXT PRIMARY KEY,
                initial_capital REAL NOT NULL,
                current_cash    REAL NOT NULL,
                realized_pnl    REAL NOT NULL DEFAULT 0,
                max_drawdown    REAL NOT NULL DEFAULT 0,
                high_watermark  REAL NOT NULL DEFAULT 0,
                created_at      TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'initialized')""")
            c.execute("""CREATE TABLE IF NOT EXISTS paper_positions (
                agent_id      TEXT NOT NULL,
                symbol        TEXT NOT NULL,
                quantity      REAL NOT NULL,
                avg_entry     REAL NOT NULL,
                current_price REAL NOT NULL,
                stop_loss_pct REAL,
                take_profit_pct REAL,
                updated_at    TEXT NOT NULL,
                PRIMARY KEY (agent_id, symbol))""")
            c.execute("""CREATE TABLE IF NOT EXISTS paper_trades (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id    TEXT NOT NULL,
                symbol      TEXT NOT NULL,
                side        TEXT NOT NULL,
                quantity    REAL NOT NULL,
                price       REAL NOT NULL,
                fee         REAL NOT NULL DEFAULT 0,
                slippage    REAL NOT NULL DEFAULT 0,
                pnl         REAL NOT NULL DEFAULT 0,
                realized    INTEGER NOT NULL DEFAULT 0,
                executed_at TEXT NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS paper_snapshots (
                agent_id       TEXT NOT NULL,
                snapshot_date  TEXT NOT NULL,
                portfolio_value REAL NOT NULL,
                pnl            REAL NOT NULL,
                drawdown_pct   REAL NOT NULL,
                PRIMARY KEY (agent_id, snapshot_date))""")
            c.execute("""CREATE TABLE IF NOT EXISTS paper_rankings (
                period_id     TEXT NOT NULL,
                rank          INTEGER NOT NULL,
                agent_id      TEXT NOT NULL,
                period_start  TEXT NOT NULL,
                period_end    TEXT NOT NULL,
                period_return REAL NOT NULL,
                updated_at    TEXT NOT NULL,
                UNIQUE (period_id, agent_id))""")
            c.execute("CREATE INDEX IF NOT EXISTS idx_trades_agent ON paper_trades(agent_id)")

    # -- portfolios -------------------------------------------------------------
    def upsert_portfolio(self, agent_id: str, initial_capital: float, status: str = "initialized") -> None:
        with self._conn() as c:
            c.execute(
                """INSERT OR IGNORE INTO paper_portfolios
                   (agent_id, initial_capital, current_cash, realized_pnl,
                    max_drawdown, high_watermark, created_at, status)
                   VALUES (?,?,?,0,0,?,datetime('now'),?)""",
                (agent_id, initial_capital, initial_capital, initial_capital, status),
            )

    def portfolio(self, agent_id: str) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM paper_portfolios WHERE agent_id=?", (agent_id,)).fetchone()
        return dict(row) if row else None

    def portfolios(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM paper_portfolios ORDER BY agent_id").fetchall()
        return [dict(r) for r in rows]

    def update_portfolio(self, agent_id: str, **fields: Any) -> None:
        allowed = {"current_cash", "realized_pnl", "max_drawdown", "high_watermark", "status"}
        assignments = ", ".join(f"{k}=?" for k in fields if k in allowed)
        if not assignments:
            return
        with self._conn() as c:
            c.execute(
                f"UPDATE paper_portfolios SET {assignments} WHERE agent_id=?",
                (*(fields[k] for k in fields if k in allowed), agent_id),
            )

    # -- positions ---------------------------------------------------------------
    def set_position(self, agent_id: str, symbol: str, **fields: Any) -> None:
        keys = tuple(k for k in ("quantity", "avg_entry", "current_price", "stop_loss_pct", "take_profit_pct", "updated_at") if k in fields)
        if not keys:
            return
        placeholders = ", ".join("?" for _ in keys)
        cols = ", ".join(keys)
        update_assignments = ", ".join(f"{k}=excluded.{k}" for k in keys)
        with self._conn() as c:
            c.execute(
                f"INSERT INTO paper_positions(agent_id, symbol, {cols}) VALUES (?,?,{placeholders}) "
                f"ON CONFLICT(agent_id, symbol) DO UPDATE SET {update_assignments}",
                (agent_id, symbol, *[fields[k] for k in keys]),
            )

    def remove_position(self, agent_id: str, symbol: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM paper_positions WHERE agent_id=? AND symbol=?", (agent_id, symbol))

    def get_position(self, agent_id: str, symbol: str) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM paper_positions WHERE agent_id=? AND symbol=?", (agent_id, symbol)).fetchone()
        return dict(row) if row else None

    def positions(self, agent_id: str) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM paper_positions WHERE agent_id=? ORDER BY symbol", (agent_id,)).fetchall()
        return [dict(r) for r in rows]

    # -- trades ---------------------------------------------------------------------
    def append_trade(
        self, agent_id: str, symbol: str, side: str, quantity: float, price: float,
        fee: float, slippage: float, pnl: float, realized: bool, executed_at: str,
    ) -> int:
        with self._conn() as c:
            cur = c.execute(
                """INSERT INTO paper_trades
                   (agent_id, symbol, side, quantity, price, fee, slippage, pnl, realized, executed_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (agent_id, symbol, side, quantity, price, fee, slippage, pnl, 1 if realized else 0, executed_at),
            )
            return int(cur.lastrowid or 0)

    def trades(self, agent_id: str | None = None, symbol: str | None = None, limit: int = 500) -> list[dict]:
        q = "SELECT * FROM paper_trades"
        vals: list[Any] = []
        if agent_id:
            q += " WHERE agent_id=?"
            vals.append(agent_id)
        if symbol:
            q += (" WHERE " if agent_id else "") + "symbol=?"
            vals.append(symbol)
        q += " ORDER BY executed_at DESC, id DESC LIMIT ?"
        vals.append(limit)
        with self._conn() as c:
            rows = c.execute(q, vals).fetchall()
        return [dict(r) for r in rows]

    def active_agents(self) -> list[str]:
        """Agent ids with at least one open position."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT DISTINCT agent_id FROM paper_positions WHERE quantity<>0 OR quantity IS NOT NULL"
            ).fetchall()
        return sorted(r[0] for r in rows)

    def count(self, table: str) -> int:
        # table is validated against an allowlist — no SQL injection surface.
        allowed = {"paper_portfolios", "paper_positions", "paper_trades", "paper_snapshots", "paper_rankings"}
        if table not in allowed:
            raise ValueError(f"unknown table {table}")
        with self._conn() as c:
            return c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    # -- snapshots / rankings --------------------------------------------------------------
    def insert_snapshot(self, agent_id: str, snapshot_date: str, portfolio_value: float, pnl: float, drawdown_pct: float) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO paper_snapshots(agent_id, snapshot_date, portfolio_value, pnl, drawdown_pct)"
                " VALUES (?,?,?,?,?)",
                (agent_id, snapshot_date, portfolio_value, pnl, drawdown_pct),
            )

    def snapshots(self, agent_id: str | None = None, limit: int = 3650) -> list[dict]:
        q = "SELECT * FROM paper_snapshots"
        vals: list[Any] = []
        if agent_id:
            q += " WHERE agent_id=?"
            vals.append(agent_id)
        q += " ORDER BY snapshot_date DESC LIMIT ?"
        vals.append(limit)
        with self._conn() as c:
            rows = c.execute(q, vals).fetchall()
        return [dict(r) for r in rows]

    def upsert_ranking(self, period_id: str, agent_id: str, period_start: str,
                       period_end: str, period_return: float) -> None:
        import datetime
        with self._conn() as c:
            c.execute(
                "INSERT INTO paper_rankings(period_id, rank, agent_id, period_start, period_end,"
                " period_return, updated_at)"
                " VALUES (?, 0, ?, ?, ?, ?, ?)",
                (period_id, agent_id, period_start, period_end, period_return,
                 datetime.datetime.now(datetime.timezone.utc).isoformat()),
            )

    def rankings(self, period_id: str) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM paper_rankings WHERE period_id=? ORDER BY period_return DESC", (period_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def store_json(self, key: str, value: Any) -> None:
        import sqlite3 as _s
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS paper_kv(key TEXT PRIMARY KEY, value TEXT)""")
            c.execute("INSERT OR REPLACE INTO paper_kv(key, value) VALUES (?,?)", (key, json.dumps(value)))
