"""Deterministic order-book reconstruction for imported research events.

This module is deliberately pure: it performs no network calls and does not
claim that supplied events are complete, live, licensed, or exchange-authentic.
A sequence gap invalidates the current book until a fresh snapshot arrives.
"""
from __future__ import annotations

import math
from typing import Any


def _positive_number(value: Any, field: str, *, allow_zero: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not math.isfinite(number) or number < 0 or (number == 0 and not allow_zero):
        qualifier = "finite and non-negative" if allow_zero else "finite and positive"
        raise ValueError(f"{field} must be {qualifier}")
    return number


def _levels(raw: Any, field: str, *, updates: bool = False) -> list[tuple[float, float]]:
    if not isinstance(raw, list) or (not updates and not raw) or len(raw) > 5000:
        raise ValueError(f"{field} must be a {'possibly empty ' if updates else 'non-empty '}array of at most 5000 levels")
    result = []
    seen = set()
    for index, level in enumerate(raw):
        if not isinstance(level, dict):
            raise ValueError(f"{field}[{index}] must be an object")
        price = _positive_number(level.get("price"), f"{field}[{index}].price")
        quantity = _positive_number(level.get("quantity"), f"{field}[{index}].quantity", allow_zero=updates)
        if price in seen:
            raise ValueError(f"{field} contains duplicate price levels")
        seen.add(price)
        result.append((price, quantity))
    return result


def _apply_side(book: dict[float, float], changes: list[tuple[float, float]]) -> None:
    for price, quantity in changes:
        if quantity == 0:
            book.pop(price, None)
        else:
            book[price] = quantity


def book_metrics(bids: dict[float, float], asks: dict[float, float], depth_bps: float = 100.0) -> dict[str, Any]:
    """Calculate spread and depth imbalance inside symmetric mid-price bands."""
    if not math.isfinite(float(depth_bps)) or not 0 < float(depth_bps) <= 10000:
        raise ValueError("depth_bps must be greater than 0 and at most 10000")
    bid_prices = sorted(bids, reverse=True)
    ask_prices = sorted(asks)
    if not bid_prices or not ask_prices:
        raise ValueError("both sides of the book must contain at least one level")
    best_bid, best_ask = bid_prices[0], ask_prices[0]
    if best_bid >= best_ask:
        raise ValueError("reconstructed book is crossed or locked")
    mid = (best_bid + best_ask) / 2
    band = float(depth_bps) / 10000
    bid_depth = sum(price * qty for price, qty in bids.items() if price >= mid * (1 - band))
    ask_depth = sum(price * qty for price, qty in asks.items() if price <= mid * (1 + band))
    total = bid_depth + ask_depth
    return {
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid_price": mid,
        "spread": best_ask - best_bid,
        "spread_bps": (best_ask - best_bid) / mid * 10000,
        "depth_band_bps": float(depth_bps),
        "bid_notional_depth": bid_depth,
        "ask_notional_depth": ask_depth,
        "depth_imbalance": (bid_depth - ask_depth) / total if total else None,
        "book_level_counts": {"bids": len(bids), "asks": len(asks)},
    }


def reconstruct_order_book(events: list[dict[str, Any]], depth_bps: float = 100.0) -> dict[str, Any]:
    """Replay snapshot/delta events in supplied order; gaps require a new snapshot.

    Event envelope fields: event_type, sequence_number, payload.
    Snapshot payload: bids/asks arrays of {price, quantity}.
    Delta payload: bids/asks arrays; quantity=0 deletes a price level.
    Every delta must have previous_sequence_number equal to the current sequence
    and sequence_number strictly greater than it. This explicit predecessor
    contract avoids assuming venue-specific sequence increments.
    """
    if not isinstance(events, list):
        raise ValueError("events must be a list")
    bids: dict[float, float] = {}
    asks: dict[float, float] = {}
    current_sequence: int | None = None
    valid = False
    gaps = []
    applied_deltas = 0
    snapshots = 0
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise ValueError(f"events[{index}] must be an object")
        kind = event.get("event_type")
        sequence = event.get("sequence_number")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            raise ValueError(f"events[{index}].sequence_number must be a non-negative integer")
        payload = event.get("payload")
        if not isinstance(payload, dict):
            raise ValueError(f"events[{index}].payload must be an object")
        if kind == "order_book_snapshot":
            next_bids = dict(_levels(payload.get("bids"), f"events[{index}].payload.bids"))
            next_asks = dict(_levels(payload.get("asks"), f"events[{index}].payload.asks"))
            bids, asks = next_bids, next_asks
            current_sequence = sequence
            valid = True
            snapshots += 1
        elif kind == "order_book_delta":
            if not valid or current_sequence is None:
                gaps.append({"event_index": index, "reason": "delta_without_valid_snapshot", "sequence_number": sequence})
                continue
            previous = event.get("previous_sequence_number")
            if previous != current_sequence or sequence <= current_sequence:
                gaps.append({
                    "event_index": index,
                    "reason": "sequence_gap",
                    "expected_previous_sequence_number": current_sequence,
                    "received_previous_sequence_number": previous,
                    "received_sequence_number": sequence,
                })
                valid = False
                bids, asks = {}, {}
                current_sequence = None
                continue
            bid_changes = _levels(payload.get("bids", []), f"events[{index}].payload.bids", updates=True)
            ask_changes = _levels(payload.get("asks", []), f"events[{index}].payload.asks", updates=True)
            _apply_side(bids, bid_changes)
            _apply_side(asks, ask_changes)
            current_sequence = sequence
            applied_deltas += 1
        else:
            raise ValueError(f"events[{index}].event_type must be order_book_snapshot or order_book_delta")

    if not valid:
        return {
            "valid": False,
            "status": "unavailable_sequence_gap_or_missing_snapshot",
            "last_sequence_number": current_sequence,
            "snapshots_applied": snapshots,
            "deltas_applied": applied_deltas,
            "sequence_gaps": gaps,
            "bids": [],
            "asks": [],
            "metrics": None,
            "data_note": "No book is returned after a sequence gap; ingest a new snapshot before resuming analysis.",
        }
    metrics = book_metrics(bids, asks, depth_bps)
    return {
        "valid": True,
        "status": "reconstructed_from_supplied_events",
        "last_sequence_number": current_sequence,
        "snapshots_applied": snapshots,
        "deltas_applied": applied_deltas,
        "sequence_gaps": gaps,
        "bids": [{"price": p, "quantity": bids[p]} for p in sorted(bids, reverse=True)],
        "asks": [{"price": p, "quantity": asks[p]} for p in sorted(asks)],
        "metrics": metrics,
        "data_note": "Replay reflects only the supplied events; it does not establish feed completeness, freshness, provider authenticity or live status.",
    }
