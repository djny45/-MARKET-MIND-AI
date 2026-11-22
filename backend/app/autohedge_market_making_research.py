"""AutoHedge-inspired market-making analysis primitives.

Research-only: this module computes candidate quotes and simulated fill outcomes
from supplied book snapshots. It never connects to an exchange, signs orders,
or submits/cancels orders.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from math import isfinite
from typing import Any


@dataclass(frozen=True)
class BookSnapshot:
    bid: float
    ask: float
    timestamp: float
    bid_size: float | None = None
    ask_size: float | None = None


@dataclass(frozen=True)
class MarketMakingResearchConfig:
    half_spread_bps: float = 5.0
    max_quote_notional: float = 1000.0
    inventory_skew_bps_per_unit: float = 0.0
    max_data_age_seconds: float = 30.0


def _positive_finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    value = float(value)
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{field} must be finite and positive")
    return value


def validate_book(snapshot: BookSnapshot, now: float, max_age: float) -> None:
    bid = _positive_finite(snapshot.bid, "bid")
    ask = _positive_finite(snapshot.ask, "ask")
    if ask < bid:
        raise ValueError("crossed or inverted market book")
    timestamp = _positive_finite(snapshot.timestamp, "timestamp")
    if not isfinite(now) or now < timestamp:
        raise ValueError("book timestamp is in the future or clock is invalid")
    if now - timestamp > max_age:
        raise ValueError("stale market-data snapshot")
    for field, value in (("bid_size", snapshot.bid_size), ("ask_size", snapshot.ask_size)):
        if value is not None and (not isfinite(float(value)) or float(value) < 0):
            raise ValueError(f"{field} must be finite and non-negative")


def calculate_research_quotes(
    snapshot: BookSnapshot,
    config: MarketMakingResearchConfig,
    now: float,
    inventory_units: float = 0.0,
) -> dict:
    """Return indicative bid/ask levels from a supplied book; these are not orders."""
    validate_book(snapshot, now, config.max_data_age_seconds)
    half_spread = _positive_finite(config.half_spread_bps, "half_spread_bps") / 10000.0
    notional = _positive_finite(config.max_quote_notional, "max_quote_notional")
    if not isfinite(inventory_units):
        raise ValueError("inventory_units must be finite")
    mid = (snapshot.bid + snapshot.ask) / 2.0
    skew = float(config.inventory_skew_bps_per_unit) * inventory_units / 10000.0
    # Shift the quote center with inventory while preserving the configured spread.
    center = mid * (1.0 - skew)
    indicative_bid = center * (1.0 - half_spread)
    indicative_ask = center * (1.0 + half_spread)
    if not isfinite(indicative_bid) or not isfinite(indicative_ask) or indicative_bid <= 0 or indicative_ask <= indicative_bid:
        raise ValueError("inventory skew produces invalid indicative quotes")
    return {
        "mode": "research_only_indicative_quotes",
        "mid_price": mid,
        "indicative_bid": indicative_bid,
        "indicative_ask": indicative_ask,
        "max_quote_notional": notional,
        "inventory_units_input": inventory_units,
        "source_timestamp": snapshot.timestamp,
        "broker_execution": False,
        "orders_submitted": False,
    }


def simulate_fill(
    side: str,
    price: float,
    quantity: float,
    quote_balance: float,
    base_balance: float,
    fee_bps: float = 0.0,
) -> dict:
    """Pure in-memory fill calculator. It does not mutate state or write order files."""
    if side not in {"buy", "sell"}:
        raise ValueError("side must be buy or sell")
    price = _positive_finite(price, "price")
    quantity = _positive_finite(quantity, "quantity")
    fee_bps = float(fee_bps)
    if not isfinite(fee_bps) or fee_bps < 0 or fee_bps >= 10000:
        raise ValueError("fee_bps must be finite and between 0 and 10000")
    quote_balance = float(quote_balance)
    base_balance = float(base_balance)
    if not isfinite(quote_balance) or not isfinite(base_balance) or min(quote_balance, base_balance) < 0:
        raise ValueError("balances must be finite and non-negative")
    gross = price * quantity
    fee = gross * fee_bps / 10000.0
    if side == "buy":
        total_cost = gross + fee
        if total_cost > quote_balance:
            return {"status": "rejected_insufficient_quote", "broker_execution": False}
        return {
            "status": "simulated_fill",
            "side": side,
            "price": price,
            "quantity": quantity,
            "fee": fee,
            "quote_balance_after": quote_balance - total_cost,
            "base_balance_after": base_balance + quantity,
            "broker_execution": False,
        }
    proceeds = gross - fee
    if quantity > base_balance:
        return {"status": "rejected_insufficient_base", "broker_execution": False}
    return {
        "status": "simulated_fill",
        "side": side,
        "price": price,
        "quantity": quantity,
        "fee": fee,
        "quote_balance_after": quote_balance + proceeds,
        "base_balance_after": base_balance - quantity,
        "broker_execution": False,
    }


def research_snapshot_to_dict(snapshot: BookSnapshot) -> dict:
    """Serialize a supplied snapshot for reports."""
    return asdict(snapshot)
