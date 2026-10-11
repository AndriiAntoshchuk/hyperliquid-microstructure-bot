from dataclasses import dataclass
from enum import Enum
from math import isfinite

from hlbot.backtest.maker import MakerFill, MakerOrder, place_maker_order, simulate_maker_fill, trade_can_fill
from hlbot.models.order_book import OrderBookSnapshot
from hlbot.models.trade import Trade

class MakerOrderStatus(str, Enum):
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"

@dataclass(frozen=True)
class MakerOrderResult:
    order: MakerOrder
    fill: MakerFill
    status: MakerOrderStatus
    end_ts: float | None

    @property
    def remaining_quantity(self) -> float:
        return self.fill.unfilled_quantity

@dataclass(frozen=True)
class PendingMakerOrder:
    order: MakerOrder
    remaining_quantity: float
    queue_ahead_remaining: float
    filled_quantity: float = 0.0
    first_fill_ts: float | None = None
    last_fill_ts: float | None = None

    def __post_init__(self):
        if self.remaining_quantity < 0: raise ValueError("remaining_quantity cannot be negative")
        if self.queue_ahead_remaining < 0: raise ValueError("queue_ahead_remaining cannot be negative")
        if self.filled_quantity < 0: raise ValueError("filled_quantity cannot be negative")

    @classmethod
    def from_order(cls, order: MakerOrder):
        return cls(
            order=order,
            remaining_quantity=order.quantity,
            queue_ahead_remaining=order.queue_ahead_quantity
        )

    @property
    def fully_filled(self) -> bool:
        tolerance = max(1e-12, self.order.quantity * 1e-12)
        return self.remaining_quantity <= tolerance

    @property
    def fill_fraction(self) -> float:
        return self.filled_quantity / self.order.quantity

def advance_pending_maker(pending: PendingMakerOrder, trades: list[Trade]) -> PendingMakerOrder:
    remaining = pending.remaining_quantity
    queue_ahead = pending.queue_ahead_remaining
    filled = pending.filled_quantity
    first_fill_ts = pending.first_fill_ts
    last_fill_ts = pending.last_fill_ts

    for trade in sorted(trades, key=lambda item: item.exchange_ts):
        if pending.fully_filled: break
        if not trade_can_fill(pending.order, trade): continue

        available = trade.quantity

        if queue_ahead > 0:
            consumed = min(queue_ahead, available)
            queue_ahead -= consumed
            available -= consumed

        if available <= 0: continue

        quantity = min(remaining, available)
        if quantity <= 0: continue

        if first_fill_ts is None: first_fill_ts = trade.exchange_ts

        filled += quantity
        remaining -= quantity
        last_fill_ts = trade.exchange_ts

        if remaining <= max(1e-12, pending.order.quantity * 1e-12):
            remaining = 0.0
            break

    return PendingMakerOrder(
        order=pending.order,
        remaining_quantity=remaining,
        queue_ahead_remaining=queue_ahead,
        filled_quantity=filled,
        first_fill_ts=first_fill_ts,
        last_fill_ts=last_fill_ts
    )

def pending_maker_fill(pending: PendingMakerOrder) -> MakerFill:
    return MakerFill(
        side=pending.order.side,
        limit_price=pending.order.limit_price,
        requested_quantity=pending.order.quantity,
        filled_quantity=pending.filled_quantity,
        queue_ahead_initial=pending.order.queue_ahead_quantity,
        queue_ahead_remaining=pending.queue_ahead_remaining,
        first_fill_ts=pending.first_fill_ts,
        last_fill_ts=pending.last_fill_ts
    )

def simulate_maker_lifecycle(
    order: MakerOrder,
    trades: list[Trade],
    max_age_seconds: float | None = None,
    cancel_ts: float | None = None
) -> MakerOrderResult:
    if max_age_seconds is not None and (not isfinite(max_age_seconds) or max_age_seconds <= 0):
        raise ValueError("max_age_seconds must be positive and finite")

    if cancel_ts is not None:
        if not isfinite(cancel_ts): raise ValueError("cancel_ts must be finite")
        if cancel_ts < order.placed_ts: raise ValueError("cancel_ts cannot be before placed_ts")

    expiry_ts = order.placed_ts + max_age_seconds if max_age_seconds is not None else None
    terminal_ts = None
    terminal_status = None

    if expiry_ts is not None:
        terminal_ts = expiry_ts
        terminal_status = MakerOrderStatus.EXPIRED

    if cancel_ts is not None and (terminal_ts is None or cancel_ts < terminal_ts):
        terminal_ts = cancel_ts
        terminal_status = MakerOrderStatus.CANCELLED

    fill = simulate_maker_fill(order, trades, end_ts=terminal_ts)

    if fill.fully_filled:
        return MakerOrderResult(order, fill, MakerOrderStatus.FILLED, fill.last_fill_ts)

    if terminal_status is not None:
        return MakerOrderResult(order, fill, terminal_status, terminal_ts)

    status = MakerOrderStatus.PARTIALLY_FILLED if fill.filled_quantity > 0 else MakerOrderStatus.OPEN
    return MakerOrderResult(order, fill, status, None)

def replace_maker_order(
    result: MakerOrderResult,
    snapshot: OrderBookSnapshot,
    limit_price: float | None = None,
    queue_ahead_fraction: float = 1.0
) -> MakerOrder:
    if result.status not in (MakerOrderStatus.CANCELLED, MakerOrderStatus.EXPIRED):
        raise ValueError("only cancelled or expired orders can be replaced")

    if result.remaining_quantity <= 0: raise ValueError("no remaining quantity to replace")
    if result.end_ts is None: raise ValueError("terminal order requires end_ts")
    if snapshot.exchange_ts < result.end_ts: raise ValueError("replacement snapshot cannot precede order end")

    return place_maker_order(
        snapshot=snapshot,
        side=result.order.side,
        quantity=result.remaining_quantity,
        limit_price=limit_price,
        queue_ahead_fraction=queue_ahead_fraction
    )