#!/usr/bin/env python3
"""Bounded read-only HTTP smoke/load probe for a private MARKET-MIND-AI deployment.

The probe sends GET requests only. It reports latency and status summaries,
never response bodies, request headers, environment variables, or credentials.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from collections import Counter


def percentile(samples: list[float], fraction: float) -> float | None:
    if not samples:
        return None
    ordered = sorted(samples)
    index = max(0, min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1))
    return round(ordered[index], 2)


def probe(url: str, timeout: float) -> tuple[float, str]:
    started = time.perf_counter()
    status = "request_error"
    try:
        request = urllib.request.Request(url, method="GET", headers={"User-Agent": "MARKET-MIND-AI-load-check/1.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = str(response.status)
            # Read a bounded amount to ensure the response completed without
            # retaining or printing application data.
            response.read(4096)
    except urllib.error.HTTPError as exc:
        status = f"http_{exc.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        status = type(exc).__name__
    elapsed_ms = (time.perf_counter() - started) * 1000
    return elapsed_ms, status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080/api/ready")
    parser.add_argument("--requests", type=int, default=120)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--max-p95-ms", type=float, default=None)
    parser.add_argument("--max-error-rate", type=float, default=0.0)
    args = parser.parse_args()

    if not (1 <= args.requests <= 5000):
        parser.error("--requests must be between 1 and 5000")
    if not (1 <= args.concurrency <= 64):
        parser.error("--concurrency must be between 1 and 64")
    if not (0.1 <= args.timeout <= 60):
        parser.error("--timeout must be between 0.1 and 60 seconds")
    if args.max_p95_ms is not None and args.max_p95_ms <= 0:
        parser.error("--max-p95-ms must be positive")
    if not (0 <= args.max_error_rate <= 1):
        parser.error("--max-error-rate must be between 0 and 1")

    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(lambda _: probe(args.url, args.timeout), range(args.requests)))
    elapsed = time.perf_counter() - started

    latencies = [item[0] for item in results]
    statuses = Counter(item[1] for item in results)
    successful = statuses.get("200", 0)
    error_count = args.requests - successful
    error_rate = error_count / args.requests
    p95 = percentile(latencies, 0.95)
    report = {
        "target_path": urlsplit(args.url).path,
        "requests": args.requests,
        "concurrency": args.concurrency,
        "elapsed_seconds": round(elapsed, 3),
        "requests_per_second": round(args.requests / elapsed, 2) if elapsed else None,
        "status_counts": dict(sorted(statuses.items())),
        "latency_ms": {
            "p50": percentile(latencies, 0.50),
            "p95": p95,
            "max": round(max(latencies), 2) if latencies else None,
        },
        "error_rate": round(error_rate, 4),
        "thresholds": {
            "max_p95_ms": args.max_p95_ms,
            "max_error_rate": args.max_error_rate,
        },
        "result": "pass" if error_rate <= args.max_error_rate and (
            args.max_p95_ms is None or (p95 is not None and p95 <= args.max_p95_ms)
        ) else "fail",
        "read_only": True,
        "response_bodies_logged": False,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["result"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
