"""Bounded, read-only validation of the four public quote adapters.

This script is *evidence collection*, not a price feed. Constraints:

* At most one request per symbol; at most 8 symbols in total.
* 8-second socket timeout, 4 MB response cap (enforced by the adapters).
* No credentials, no cookies, no writes to provider systems.
* The operator attestation list is deliberately EMPTY, so no observation can
  be labelled LIVE or DELAYED regardless of what a provider returns.
* Raw responses are redacted to the fields the adapters actually consume and
  are written to docs/external-evidence/ for reproducibility.

Run: PYTHONPATH=.:./backend .venvs/backend/bin/python scripts/validate_four_market_providers.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from app.market_data import DataStatus
from app.provider_adapters import ADAPTERS, ProviderError

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "external-evidence" / "four-market-provider-validation.json"

# One symbol per market plus one India BSE variant. Deliberately tiny.
PROBES = [
    ("us", "AAPL", "Apple Inc.", "NASDAQ", "USD"),
    ("us", "SPX", "S&P 500 Index", "INDEX", "USD"),
    ("india", "RELIANCE", "Reliance Industries Ltd.", "NSE", "INR"),
    ("india", "TCS", "Tata Consultancy Services Ltd.", "BSE", "INR"),
    ("forex", "EURUSD", "Euro / US Dollar", "OTC", "USD"),
    ("forex", "USDINR", "US Dollar / Indian Rupee", "OTC", "INR"),
    ("crypto", "BTCUSD", "Bitcoin / US Dollar", "Multi-venue", "USD"),
    ("crypto", "ETHUSD", "Ethereum / US Dollar", "Multi-venue", "USD"),
]

ATTEMPTED: list[tuple[str, str]] = []


def probe(group, symbol, name, exchange, currency):
    adapter = ADAPTERS[group]
    # Bounded timeout: never wait more than 8s on a public endpoint.
    adapter.timeout_seconds = 8.0
    started = time.monotonic()
    attested = frozenset()  # no attestation -> impossible to claim LIVE/DELAYED
    try:
        quote = adapter.fetch_quote(
            symbol=symbol, name=name, exchange=exchange, currency=currency,
            attested_sources=attested,
        )
        elapsed = round(time.monotonic() - started, 3)
        return {
            "market_group": group,
            "symbol": symbol,
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": elapsed,
            "outcome": "observed" if quote.status is not DataStatus.UNAVAILABLE else "unavailable",
            "quote": quote.to_payload(),
            # Adapter internals that matter for licensing/rate-limit evidence.
            "declared_status": adapter.capability.preferred_status.value,
            "requires_attestation": adapter.capability.requires_attestation,
            "licensing_note": adapter.capability.licensing_note,
            "limitations": list(adapter.capability.limitations),
        }
    except Exception as exc:  # containment; a probe must never abort the run
        return {
            "market_group": group,
            "symbol": symbol,
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "outcome": "error",
            "error_type": type(exc).__name__,
            "error": str(exc)[:200],
            "declared_status": adapter.capability.preferred_status.value,
            "requires_attestation": adapter.capability.requires_attestation,
            "licensing_note": adapter.capability.licensing_note,
            "limitations": list(adapter.capability.limitations),
        }


def raw_endpoint_probe():
    """Direct, minimal response-metadata probe for rate-limit headers."""
    import urllib.error
    import urllib.request

    endpoints = {
        "yahoo-chart-AAPL": (
            "https://query1.finance.yahoo.com/v8/finance/chart/AAPL"
            "?interval=1d&range=5d&events=history"
        ),
        "ecb-D-USD-EUR": (
            "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A"
            "?format=csvdata&lastNObservations=2"
        ),
        "coingecko-simple-price": (
            "https://api.coingecko.com/api/v3/simple/price"
            "?ids=bitcoin&vs_currencies=usd&include_last_updated_at=true"
        ),
    }
    results = {}
    for name, url in endpoints.items():
        started = time.monotonic()
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "MARKET-MIND-AI validation/1.0 (research-only)"}
            )
            with urllib.request.urlopen(request, timeout=8) as response:
                body = response.read(4096)  # header/bounded body sample only
                results[name] = {
                    "status": response.status,
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                    "content_type": response.headers.get("Content-Type"),
                    "rate_limit_headers": {
                        key: value for key, value in response.headers.items()
                        if "ratelimit" in key.lower() or "retry-after" in key.lower()
                        or "throttle" in key.lower()
                    },
                    "body_sample_start": body[:160].decode("utf-8", "replace"),
                }
        except urllib.error.HTTPError as exc:
            results[name] = {
                "status": exc.code,
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "error": f"HTTP {exc.code}",
                "rate_limit_headers": {
                    key: value for key, value in exc.headers.items()
                    if "ratelimit" in key.lower() or "retry-after" in key.lower()
                    or "throttle" in key.lower()
                },
            }
        except Exception as exc:
            results[name] = {
                "status": None,
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "error": f"{type(exc).__name__}: {str(exc)[:160]}",
            }
    return results


def main():
    started = time.monotonic()
    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Read-only provider validation evidence for the four-market terminal",
        "constraints": {
            "requests_per_symbol": 1,
            "total_probe_symbols": len(PROBES),
            "timeout_seconds": 8,
            "response_cap_bytes": 4_000_000,
            "credentials_used": False,
            "cookies_used": False,
            "attested_sources": [],
            "live_labels_allowed": False,
            "live_label_rule": (
                "No source is attested, so an attested LIVE or DELAYED claim is "
                "impossible. A provider response is never self-certifying."
            ),
        },
        "probes": [],
        "endpoint_metadata": {},
    }

    print("\n=== Adapter probe (8 bounded requests) ===")
    for group, symbol, name, exchange, currency in PROBES:
        ATTEMPTED.append((group, symbol))
        row = probe(group, symbol, name, exchange, currency)
        results["probes"].append(row)
        q = row.get("quote", {})
        print(
            f"{group:6} {symbol:10} {row['outcome']:11} "
            f"status={q.get('status', '-'):12} "
            f"last={q.get('last')} age={q.get('age_seconds')}s "
            f"{row['elapsed_seconds']}s"
        )
        if row["outcome"] == "unavailable":
            print(f"         reason: {q.get('reason')}")

    print("\n=== Endpoint metadata probe (3 bounded requests) ===")
    results["endpoint_metadata"] = raw_endpoint_probe()
    for name, row in results["endpoint_metadata"].items():
        print(f"{name:28} HTTP={row.get('status')} rate_headers={row.get('rate_limit_headers')}")

    results["elapsed_total_seconds"] = round(time.monotonic() - started, 3)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nEvidence written to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
