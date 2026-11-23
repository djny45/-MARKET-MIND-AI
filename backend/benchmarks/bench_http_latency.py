"""End-to-end HTTP latency comparison: rollback journal vs WAL.

Seeds a temporary database with 20k market bars, starts the real FastAPI app in
a subprocess for each journal mode, has a writer issue a fixed number of
commits while a read probe runs, and reports latency percentiles from
``scripts/load_check.py``.

Read-only against the project; all data lives in a temporary directory.

Usage: PYTHONPATH=backend python -m backend.benchmarks.bench_http_latency
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = "/api/market-data/lineage?symbol=BENCH00&interval=1d&limit=200"
REQUESTS = 400
CONCURRENCY = 8
WRITE_BATCHES = 400
SYMBOLS = 40
BARS_PER_SYMBOL = 500
START = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _batch(symbol: str, offset: int, count: int, *, backwards: bool = False):
    from app.market_data import MarketDataBatch, OHLCVBar

    # Writer batches walk backwards from 2024 so every commit inserts a new row
    # and no bar timestamp can land after retrieved_at.
    base = START - timedelta(days=offset + count) if backwards else START
    bars = [
        OHLCVBar(
            timestamp=base + timedelta(days=offset + n),
            open=100.0, high=101.0, low=99.0, close=100.5, volume=1000.0 + n,
        )
        for n in range(count)
    ]
    return MarketDataBatch(
        symbol=symbol, interval="1d", status="historical", source="benchmark",
        retrieved_at=datetime.now(timezone.utc), bars=bars,
    )


def _seed(database: Path) -> int:
    from app import market_store

    rows = 0
    for symbol_index in range(SYMBOLS):
        symbol = f"BENCH{symbol_index:02d}"
        for offset in range(0, BARS_PER_SYMBOL, 100):
            batch = _batch(symbol, offset, min(100, BARS_PER_SYMBOL - offset))
            market_store.store_batch(batch)
            rows += len(batch.bars)
    return rows


def _writer(stop: threading.Event, counters: dict) -> None:
    """Issue a fixed number of commits while the read probe runs."""
    from app import market_store

    attempt = 0
    while not stop.is_set() and attempt < WRITE_BATCHES:
        batch = _batch("WRITER00", attempt + 1, 1, backwards=True)
        try:
            market_store.store_batch(batch)
            counters["writes"] = counters.get("writes", 0) + 1
        except Exception as exc:  # pragma: no cover - reported, not asserted
            counters["write_errors"] = counters.get("write_errors", 0) + 1
            counters["last_error"] = type(exc).__name__
        attempt += 1
    counters["write_attempts"] = attempt


def _probe(port: int) -> dict:
    process = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "load_check.py"),
         "--url", f"http://127.0.0.1:{port}{PROBE_PATH}",
         "--requests", str(REQUESTS), "--concurrency", str(CONCURRENCY),
         "--timeout", "5"],
        capture_output=True, text=True, timeout=300,
    )
    text = process.stdout.strip()
    if not text:
        return {"error": (process.stderr or "no output")[-300:]}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error": text[-300:]}


def _wait_ready(port: int, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.3)
    raise RuntimeError("server did not become ready")


def run(wal: bool) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        database = Path(tmp) / "bench.db"
        environment = dict(os.environ)
        environment["MARKET_MIND_DB"] = str(database)
        environment["MARKET_MIND_SQLITE_WAL"] = "1" if wal else "0"
        environment["PYTHONPATH"] = str(ROOT / "backend")
        os.environ["MARKET_MIND_DB"] = str(database)
        os.environ["MARKET_MIND_SQLITE_WAL"] = environment["MARKET_MIND_SQLITE_WAL"]
        sys.path.insert(0, str(ROOT / "backend"))
        seeded = _seed(database)

        port = _free_port()
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app",
             "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
            cwd=str(ROOT), env=environment,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        counters: dict = {}
        try:
            _wait_ready(port)
            stop = threading.Event()
            writer = threading.Thread(target=_writer, args=(stop, counters), daemon=True)
            writer.start()
            try:
                probe = _probe(port)
            finally:
                stop.set()
                writer.join(timeout=30)
        finally:
            server.terminate()
            try:
                server.wait(timeout=20)
            except subprocess.TimeoutExpired:  # pragma: no cover
                server.kill()
        return {
            "mode": "wal" if wal else "rollback_journal",
            "seeded_bars": seeded,
            "write_attempts": counters.get("write_attempts", 0),
            "concurrent_writes": counters.get("writes", 0),
            "write_errors": counters.get("write_errors", 0),
            "probe": probe,
        }


def main() -> int:
    for wal in (False, True):
        result = run(wal)
        probe = result["probe"]
        print(json.dumps({
            "mode": result["mode"],
            "seeded_bars": result["seeded_bars"],
            "write_attempts": result["write_attempts"],
            "committed_writes": result["concurrent_writes"],
            "write_errors": result["write_errors"],
            "http_p50_ms": probe.get("latency_ms", {}).get("p50"),
            "http_p95_ms": probe.get("latency_ms", {}).get("p95"),
            "http_max_ms": probe.get("latency_ms", {}).get("max"),
            "requests_per_second": probe.get("requests_per_second"),
            "error_rate": probe.get("error_rate"),
            "error": probe.get("error"),
        }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
