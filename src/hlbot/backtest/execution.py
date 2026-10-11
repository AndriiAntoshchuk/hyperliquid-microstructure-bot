from dataclasses import dataclass
from math import isfinite

from hlbot.models.order_book import OrderBookSnapshot
from hlbot.models.trade import TradeSide
from hlbot.strategy.order_intent import OrderIntent
from hlbot.strategy.signal import SignalDirection

@dataclass(frozen=True)
class SimulatedFill:
    side: TradeSide
    timestamp: float
    requested_notional: float
    filled_notional: float
    requested_quantity: float | None
    filled_quantity: float
    average_price: float | None
    reference_mid_price: float
    slippage_bps: float
    levels_consumed: int
    fully_filled: bool

    def __post_init__(self):
        for name in ("timestamp", "requested_notional", "filled_notional", "filled_quantity", "reference_mid_price", "slippage_bps"):
            if not isfinite(getattr(self, name)): raise ValueError(f"{name} must be finite")

        if self.requested_notional < 0: raise ValueError("requested_notional cannot be negative")
        if self.requested_quantity is not None and (not isfinite(self.requested_quantity) or self.requested_quantity <= 0): raise ValueError("requested_quantity must be positive and finite")
        if self.requested_notional == 0 and self.requested_quantity is None: raise ValueError("fill must request notional or quantity")
        if self.filled_notional < 0 or self.filled_quantity < 0: raise ValueError("filled values cannot be negative")
        if self.reference_mid_price <= 0: raise ValueError("reference_mid_price must be positive")
        if self.levels_consumed < 0: raise ValueError("levels_consumed cannot be negative")
        if self.filled_quantity == 0 and self.average_price is not None: raise ValueError("empty fill cannot have average_price")
        if self.filled_quantity > 0 and self.average_price is None: raise ValueError("non-empty fill requires average_price")

    @property
    def unfilled_notional(self) -> float:
        return max(0.0, self.requested_notional - self.filled_notional)

    @property
    def unfilled_quantity(self) -> float:
        if self.requested_quantity is None: return 0.0
        return max(0.0, self.requested_quantity - self.filled_quantity)

    @property
    def fill_fraction(self) -> float:
        if self.requested_quantity is not None: return self.filled_quantity / self.requested_quantity
        return self.filled_notional / self.requested_notional

def entry_side(direction: SignalDirection) -> TradeSide:
    if direction == SignalDirection.LONG: return TradeSide.BUY
    if direction == SignalDirection.SHORT: return TradeSide.SELL
    raise ValueError("NONE direction has no execution side")

def exit_side(direction: SignalDirection) -> TradeSide:
    if direction == SignalDirection.LONG: return TradeSide.SELL
    if direction == SignalDirection.SHORT: return TradeSide.BUY
    raise ValueError("NONE direction has no execution side")

def execution_levels(snapshot: OrderBookSnapshot, side: TradeSide):
    if side == TradeSide.BUY: return snapshot.asks
    if side == TradeSide.SELL: return snapshot.bids
    raise ValueError(f"Unsupported trade side: {side}")

def execution_slippage_bps(side: TradeSide, average_price: float, mid_price: float) -> float:
    if side == TradeSide.BUY: return (average_price - mid_price) / mid_price * 10_000
    if side == TradeSide.SELL: return (mid_price - average_price) / mid_price * 10_000
    raise ValueError(f"Unsupported trade side: {side}")

def _build_fill(
    snapshot: OrderBookSnapshot,
    side: TradeSide,
    requested_notional: float,
    requested_quantity: float | None,
    filled_notional: float,
    filled_quantity: float,
    levels_consumed: int,
    fully_filled: bool
) -> SimulatedFill:
    average_price = filled_notional / filled_quantity if filled_quantity > 0 else None
    slippage_bps = execution_slippage_bps(side, average_price, snapshot.mid_price) if average_price is not None else 0.0

    return SimulatedFill(
        side=side,
        timestamp=snapshot.exchange_ts,
        requested_notional=requested_notional,
        filled_notional=filled_notional,
        requested_quantity=requested_quantity,
        filled_quantity=filled_quantity,
        average_price=average_price,
        reference_mid_price=snapshot.mid_price,
        slippage_bps=slippage_bps,
        levels_consumed=levels_consumed,
        fully_filled=fully_filled
    )

def simulate_notional_order(snapshot: OrderBookSnapshot, side: TradeSide, requested_notional: float) -> SimulatedFill:
    if not isfinite(requested_notional) or requested_notional <= 0: raise ValueError("requested_notional must be positive and finite")

    remaining = requested_notional
    filled_notional = 0.0
    filled_quantity = 0.0
    levels_consumed = 0

    for level in execution_levels(snapshot, side):
        if remaining <= 0: break

        level_notional = level.price * level.quantity
        take_notional = min(remaining, level_notional)
        take_quantity = take_notional / level.price

        if take_quantity <= 0: continue

        filled_notional += take_notional
        filled_quantity += take_quantity
        remaining -= take_notional
        levels_consumed += 1

    tolerance = max(1e-9, requested_notional * 1e-12)

    return _build_fill(
        snapshot,
        side,
        requested_notional,
        None,
        filled_notional,
        filled_quantity,
        levels_consumed,
        remaining <= tolerance
    )

def simulate_quantity_order(snapshot: OrderBookSnapshot, side: TradeSide, requested_quantity: float) -> SimulatedFill:
    if not isfinite(requested_quantity) or requested_quantity <= 0: raise ValueError("requested_quantity must be positive and finite")

    remaining = requested_quantity
    filled_notional = 0.0
    filled_quantity = 0.0
    levels_consumed = 0

    for level in execution_levels(snapshot, side):
        if remaining <= 0: break

        take_quantity = min(remaining, level.quantity)
        if take_quantity <= 0: continue

        filled_quantity += take_quantity
        filled_notional += take_quantity * level.price
        remaining -= take_quantity
        levels_consumed += 1

    tolerance = max(1e-12, requested_quantity * 1e-12)

    return _build_fill(
        snapshot,
        side,
        0.0,
        requested_quantity,
        filled_notional,
        filled_quantity,
        levels_consumed,
        remaining <= tolerance
    )

def simulate_market_order(snapshot: OrderBookSnapshot, intent: OrderIntent) -> SimulatedFill:
    return simulate_notional_order(snapshot, entry_side(intent.direction), intent.notional)

def simulate_exit_order(snapshot: OrderBookSnapshot, direction: SignalDirection, quantity: float) -> SimulatedFill:
    return simulate_quantity_order(snapshot, exit_side(direction), quantity)