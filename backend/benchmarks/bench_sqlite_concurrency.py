"""Measure SQLite concurrency cost: rollback journal (default) vs WAL.

Runs the same mixed read/write workload twice against identical temporary
databases and prints throughput and latency percentiles. Read-only; writes go
only to a temporary directory.

Usage: python -m backend.benchmarks.bench_sqlite_concurrency
"""
from __future__ import annotations

import os
import sqlite3
import statistics
import tempfile
import threading
import time
from pathlib import Path

READERS = 4
READS_PER_READER = 150
WRITER_BATCHES = 60
BARS_PER_BATCH = 20

SCHEMA = """
CREATE TABLE IF NOT EXISTS market_bars (
    symbol TEXT NOT NULL, interval TEXT NOT NULL, timestamp TEXT NOT NULL,
    open REAL NOT NULL, high REAL NOT NULL, low REAL NOT NULL, close REAL NOT NULL,
    volume REAL NOT NULL, status TEXT NOT NULL, source TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    PRIMARY KEY (symbol, interval, timestamp, source)
);
CREATE INDEX IF NOT EXISTS idx_market_bars_lookup ON market_bars(symbol, interval, timestamp);
"""


def _connect(path: str, wal: bool) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=10)
    if wal:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    return connection


def _writer(path: str, wal: bool, latencies: list[float], stop: threading.Event) -> None:
    connection = _connect(path, wal)
    try:
        for batch in range(WRITER_BATCHES):
            started = time.perf_counter()
            connection.executemany(
                "INSERT OR REPLACE INTO market_bars VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [
                    (
                        f"SYM{(batch * BARS_PER_BATCH + n) % 50}", "1d",
                        f"2026-01-{(n % 28) + 1:02d}T00:00:00+00:00",
                        100.0, 101.0, 99.0, 100.5, 1000.0 + n, "historical",
                        "bench", "2026-01-01T00:00:00+00:00",
                    )
                    for n in range(BARS_PER_BATCH)
                ],
            )
            connection.commit()
            latencies.append((time.perf_counter() - started) * 1000)
    finally:
        connection.close()
        stop.set()


def _reader(path: str, wal: bool, latencies: list[float], errors: list[str]) -> None:
    connection = _connect(path, wal)
    try:
        for n in range(READS_PER_READER):
            started = time.perf_counter()
            try:
                connection.execute(
                    "SELECT timestamp, close FROM market_bars "
                    "WHERE symbol = ? AND interval = ? ORDER BY timestamp DESC LIMIT 200",
                    (f"SYM{n % 50}", "1d"),
                ).fetchall()
            except sqlite3.Error as exc:  # pragma: no cover - measured, not asserted
                errors.append(type(exc).__name__)
            latencies.append((time.perf_counter() - started) * 1000)
    finally:
        connection.close()


def run(wal: bool) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "bench.db")
        _connect(path, wal).close()  # create schema before timing
        read_latencies: list[float] = []
        write_latencies: list[float] = []
        errors: list[str] = []
        stop = threading.Event()
        started = time.perf_counter()
        threads = [
            threading.Thread(target=_reader, args=(path, wal, read_latencies, errors))
            for _ in range(READERS)
        ]
        threads.append(threading.Thread(target=_writer, args=(path, wal, write_latencies, stop)))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        elapsed = time.perf_counter() - started
    read_latencies.sort()
    return {
        "mode": "wal" if wal else "rollback_journal",
        "wall_seconds": round(elapsed, 3),
        "reads": len(read_latencies),
        "writes": len(write_latencies),
        "read_p50_ms": round(statistics.median(read_latencies), 3),
        "read_p95_ms": round(read_latencies[int(len(read_latencies) * 0.95) - 1], 3),
        "read_max_ms": round(read_latencies[-1], 3),
        "write_p50_ms": round(statistics.median(write_latencies), 3),
        "write_p95_ms": round(write_latencies[int(len(write_latencies) * 0.95) - 1], 3),
        "errors": len(errors),
        "reads_per_second": round(len(read_latencies) / elapsed, 1),
    }


def main() -> int:
    os.environ.pop("MARKET_MIND_DB", None)
    baseline = run(wal=False)
    tuned = run(wal=True)
    for row in (baseline, tuned):
        print(
            f"{row['mode']:>17}: {row['reads_per_second']:>8} reads/s | "
            f"read p50 {row['read_p50_ms']:>7} ms | p95 {row['read_p95_ms']:>7} ms | "
            f"max {row['read_max_ms']:>7} ms | write p50 {row['write_p50_ms']:>6} ms | "
            f"errors {row['errors']}"
        )
    speedup = tuned["reads_per_second"] / baseline["reads_per_second"] if baseline["reads_per_second"] else 0
    p95 = baseline["read_p95_ms"] / tuned["read_p95_ms"] if tuned["read_p95_ms"] else 0
    print(f"\nread throughput x{speedup:.2f}, read p95 cut x{p95:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
