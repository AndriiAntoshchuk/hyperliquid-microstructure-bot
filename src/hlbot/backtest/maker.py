from dataclasses import dataclass
from math import isfinite

from hlbot.models.order_book import OrderBookSnapshot
from hlbot.models.trade import Trade, TradeSide

@dataclass(frozen=True)
class MakerOrder:
    side: TradeSide
    limit_price: float
    quantity: float
    placed_ts: float
    queue_ahead_quantity: float

    def __post_init__(self):
        if not isfinite(self.limit_price) or self.limit_price <= 0: raise ValueError("limit_price must be positive and finite")
        if not isfinite(self.quantity) or self.quantity <= 0: raise ValueError("quantity must be positive and finite")
        if not isfinite(self.placed_ts): raise ValueError("placed_ts must be finite")
        if not isfinite(self.queue_ahead_quantity) or self.queue_ahead_quantity < 0: raise ValueError("queue_ahead_quantity must be finite and non-negative")

@dataclass(frozen=True)
class MakerFill:
    side: TradeSide
    limit_price: float
    requested_quantity: float
    filled_quantity: float
    queue_ahead_initial: float
    queue_ahead_remaining: float
    first_fill_ts: float | None
    last_fill_ts: float | None

    @property
    def filled_notional(self) -> float:
        return self.filled_quantity * self.limit_price

    @property
    def unfilled_quantity(self) -> float:
        return max(0.0, self.requested_quantity - self.filled_quantity)

    @property
    def fill_fraction(self) -> float:
        return self.filled_quantity / self.requested_quantity

    @property
    def fully_filled(self) -> bool:
        tolerance = max(1e-12, self.requested_quantity * 1e-12)
        return self.unfilled_quantity <= tolerance

def visible_quantity_at_price(snapshot: OrderBookSnapshot, side: TradeSide, price: float) -> float:
    levels = snapshot.bids if side == TradeSide.BUY else snapshot.asks

    for level in levels:
        if level.price == price: return level.quantity

    return 0.0

def default_maker_price(snapshot: OrderBookSnapshot, side: TradeSide) -> float:
    if side == TradeSide.BUY: return snapshot.bids[0].price
    if side == TradeSide.SELL: return snapshot.asks[0].price
    raise ValueError(f"unsupported side: {side}")

def place_maker_order(
    snapshot: OrderBookSnapshot,
    side: TradeSide,
    quantity: float,
    limit_price: float | None = None,
    queue_ahead_fraction: float = 1.0
) -> MakerOrder:
    if not isfinite(quantity) or quantity <= 0: raise ValueError("quantity must be positive and finite")
    if not isfinite(queue_ahead_fraction) or queue_ahead_fraction < 0: raise ValueError("queue_ahead_fraction must be finite and non-negative")

    price = default_maker_price(snapshot, side) if limit_price is None else limit_price

    if side == TradeSide.BUY and price >= snapshot.asks[0].price: raise ValueError("buy maker order cannot cross the ask")
    if side == TradeSide.SELL and price <= snapshot.bids[0].price: raise ValueError("sell maker order cannot cross the bid")

    queue_ahead = visible_quantity_at_price(snapshot, side, price) * queue_ahead_fraction

    return MakerOrder(
        side=side,
        limit_price=price,
        quantity=quantity,
        placed_ts=snapshot.exchange_ts,
        queue_ahead_quantity=queue_ahead
    )

def trade_can_fill(order: MakerOrder, trade: Trade) -> bool:
    if trade.exchange_ts < order.placed_ts: return False

    if order.side == TradeSide.BUY:
        return trade.side == TradeSide.SELL and trade.price <= order.limit_price

    if order.side == TradeSide.SELL:
        return trade.side == TradeSide.BUY and trade.price >= order.limit_price

    return False

def simulate_maker_fill(order: MakerOrder, trades: list[Trade], end_ts: float | None = None) -> MakerFill:
    queue_remaining = order.queue_ahead_quantity
    order_remaining = order.quantity
    filled_quantity = 0.0
    first_fill_ts = None
    last_fill_ts = None

    for trade in sorted(trades, key=lambda item: item.exchange_ts):
        if end_ts is not None and trade.exchange_ts > end_ts: break
        if not trade_can_fill(order, trade): continue

        available = trade.quantity

        if queue_remaining > 0:
            consumed = min(queue_remaining, available)
            queue_remaining -= consumed
            available -= consumed

        if available <= 0: continue

        filled = min(order_remaining, available)
        if filled <= 0: continue

        if first_fill_ts is None: first_fill_ts = trade.exchange_ts

        filled_quantity += filled
        order_remaining -= filled
        last_fill_ts = trade.exchange_ts

        if order_remaining <= max(1e-12, order.quantity * 1e-12): break

    return MakerFill(
        side=order.side,
        limit_price=order.limit_price,
        requested_quantity=order.quantity,
        filled_quantity=filled_quantity,
        queue_ahead_initial=order.queue_ahead_quantity,
        queue_ahead_remaining=queue_remaining,
        first_fill_ts=first_fill_ts,
        last_fill_ts=last_fill_ts
    )