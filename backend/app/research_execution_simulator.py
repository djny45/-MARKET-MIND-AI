"""Deterministic synthetic-only execution lifecycle simulator.

This module has no network, exchange, broker, wallet, signing, or persistence
integration. It is intended for reproducible research fixtures only.
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Iterable


class OrderState(str, Enum):
    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


TERMINAL_STATES = {OrderState.FILLED, OrderState.CANCELLED, OrderState.REJECTED, OrderState.EXPIRED}
ALLOWED_TRANSITIONS = {
    OrderState.NEW: {OrderState.ACKNOWLEDGED, OrderState.REJECTED, OrderState.CANCELLED, OrderState.EXPIRED},
    OrderState.ACKNOWLEDGED: {OrderState.PARTIALLY_FILLED, OrderState.FILLED, OrderState.CANCELLED, OrderState.REJECTED, OrderState.EXPIRED},
    OrderState.PARTIALLY_FILLED: {OrderState.PARTIALLY_FILLED, OrderState.FILLED, OrderState.CANCELLED, OrderState.EXPIRED},
}


def _decimal(value, field_name):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field_name} must be a finite decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{field_name} must be a finite decimal")
    return result


def _aware(value, field_name="timestamp"):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


@dataclass(frozen=True)
class SimulatedFill:
    quantity: Decimal
    price: Decimal
    fee_rate: Decimal = Decimal("0")
    slippage_rate: Decimal = Decimal("0")

    @classmethod
    def create(cls, quantity, price, fee_rate=0, slippage_rate=0):
        q, p = _decimal(quantity, "quantity"), _decimal(price, "price")
        fee, slip = _decimal(fee_rate, "fee_rate"), _decimal(slippage_rate, "slippage_rate")
        if q <= 0 or p <= 0 or fee < 0 or slip < 0 or slip >= 1:
            raise ValueError("fill quantity/price must be positive; fee non-negative; slippage in [0, 1)")
        return cls(q, p, fee, slip)

    @property
    def execution_price(self):
        return self.price * (Decimal("1") + self.slippage_rate)


@dataclass
class SimulatedOrder:
    order_id: str
    idempotency_key: str
    quantity: Decimal
    state: OrderState = OrderState.NEW
    filled_quantity: Decimal = Decimal("0")
    gross_value: Decimal = Decimal("0")
    fees: Decimal = Decimal("0")
    events: list[dict] = field(default_factory=list)


class SimulationLedger:
    """In-memory fixture ledger. Reusing an idempotency key returns the prior order."""

    def __init__(self):
        self.orders: dict[str, SimulatedOrder] = {}
        self.keys: dict[str, str] = {}

    def create_order(self, order_id: str, idempotency_key: str, quantity):
        if not order_id or not idempotency_key:
            raise ValueError("order_id and idempotency_key are required")
        q = _decimal(quantity, "quantity")
        if q <= 0:
            raise ValueError("quantity must be positive")
        if idempotency_key in self.keys:
            return self.orders[self.keys[idempotency_key]]
        if order_id in self.orders:
            raise ValueError("order_id already exists")
        order = SimulatedOrder(order_id, idempotency_key, q)
        self.orders[order_id] = order
        self.keys[idempotency_key] = order_id
        return order

    def transition(self, order_id: str, target: OrderState | str, timestamp: datetime, fill: SimulatedFill | None = None):
        if order_id not in self.orders:
            raise ValueError("unknown simulated order")
        order = self.orders[order_id]
        target = OrderState(target)
        when = _aware(timestamp).isoformat()
        if target not in ALLOWED_TRANSITIONS.get(order.state, set()):
            raise ValueError(f"invalid transition: {order.state.value} -> {target.value}")
        if target in {OrderState.PARTIALLY_FILLED, OrderState.FILLED}:
            if fill is None:
                raise ValueError("fill details are required for fill transitions")
            new_filled = order.filled_quantity + fill.quantity
            if new_filled > order.quantity:
                raise ValueError("cumulative fill exceeds order quantity")
            if target == OrderState.FILLED and new_filled != order.quantity:
                raise ValueError("FILLED requires cumulative quantity to equal order quantity")
            if target == OrderState.PARTIALLY_FILLED and new_filled >= order.quantity:
                raise ValueError("use FILLED when cumulative quantity equals order quantity")
            execution_price = fill.execution_price
            order.filled_quantity = new_filled
            order.gross_value += fill.quantity * execution_price
            order.fees += fill.quantity * execution_price * fill.fee_rate
        elif fill is not None:
            raise ValueError("fill details are not accepted for non-fill transitions")
        order.state = target
        order.events.append({"state": target.value, "timestamp": when,
                             "filled_quantity": str(order.filled_quantity),
                             "gross_value": str(order.gross_value), "fees": str(order.fees)})
        return order

    def snapshot(self, order_id: str):
        if order_id not in self.orders:
            raise ValueError("unknown simulated order")
        order = self.orders[order_id]
        return {"order_id": order.order_id, "state": order.state.value,
                "quantity": str(order.quantity), "filled_quantity": str(order.filled_quantity),
                "gross_value": str(order.gross_value), "fees": str(order.fees),
                "events": [dict(event) for event in order.events]}
