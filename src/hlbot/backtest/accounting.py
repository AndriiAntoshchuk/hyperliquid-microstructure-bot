from dataclasses import dataclass
from math import isfinite

from hlbot.backtest.execution import SimulatedFill, entry_side, exit_side
from hlbot.strategy.signal import SignalDirection

@dataclass(frozen=True)
class BacktestPosition:
    direction: SignalDirection
    quantity: float
    average_entry_price: float
    realized_pnl_gross: float = 0.0
    fees_paid: float = 0.0

    def __post_init__(self):
        if self.direction == SignalDirection.NONE: raise ValueError("position direction cannot be NONE")
        if not isfinite(self.quantity) or self.quantity < 0: raise ValueError("quantity must be finite and non-negative")
        if not isfinite(self.average_entry_price) or self.average_entry_price < 0: raise ValueError("average_entry_price must be finite and non-negative")
        if not isfinite(self.realized_pnl_gross): raise ValueError("realized_pnl_gross must be finite")
        if not isfinite(self.fees_paid): raise ValueError("fees_paid must be finite")
        if self.quantity > 0 and self.average_entry_price <= 0: raise ValueError("open position requires positive average_entry_price")
        if self.quantity == 0 and self.average_entry_price != 0: raise ValueError("flat position must have average_entry_price 0")

    @property
    def is_flat(self) -> bool:
        return self.quantity == 0

    @property
    def realized_pnl_net(self) -> float:
        return self.realized_pnl_gross - self.fees_paid

def fee_amount(notional: float, fee_bps: float) -> float:
    if not isfinite(notional) or notional < 0: raise ValueError("notional must be finite and non-negative")
    if not isfinite(fee_bps): raise ValueError("fee_bps must be finite")
    return notional * fee_bps / 10_000

def open_position(direction: SignalDirection, fill: SimulatedFill, fee_bps: float) -> BacktestPosition:
    if fill.side != entry_side(direction): raise ValueError("fill side does not match entry direction")
    if fill.filled_quantity <= 0 or fill.average_price is None: raise ValueError("entry fill must contain executed quantity")

    return BacktestPosition(
        direction,
        fill.filled_quantity,
        fill.average_price,
        fees_paid=fee_amount(fill.filled_notional, fee_bps)
    )

def scale_position(position: BacktestPosition, fill: SimulatedFill, fee_bps: float) -> BacktestPosition:
    if position.is_flat: raise ValueError("cannot scale a flat position")
    if fill.side != entry_side(position.direction): raise ValueError("fill side does not match scale-in direction")
    if fill.filled_quantity <= 0 or fill.average_price is None: raise ValueError("scale-in fill must contain executed quantity")

    quantity = position.quantity + fill.filled_quantity
    average_price = (
        position.quantity * position.average_entry_price
        + fill.filled_quantity * fill.average_price
    ) / quantity

    return BacktestPosition(
        position.direction,
        quantity,
        average_price,
        position.realized_pnl_gross,
        position.fees_paid + fee_amount(fill.filled_notional, fee_bps)
    )

def close_position(position: BacktestPosition, fill: SimulatedFill, fee_bps: float) -> BacktestPosition:
    if position.is_flat: raise ValueError("cannot close a flat position")
    if fill.side != exit_side(position.direction): raise ValueError("fill side does not match exit direction")
    if fill.filled_quantity <= 0 or fill.average_price is None: raise ValueError("exit fill must contain executed quantity")

    tolerance = max(1e-12, position.quantity * 1e-12)
    if fill.filled_quantity - position.quantity > tolerance: raise ValueError("exit fill exceeds position quantity")

    sign = 1 if position.direction == SignalDirection.LONG else -1
    realized = sign * (fill.average_price - position.average_entry_price) * fill.filled_quantity

    remaining = position.quantity - fill.filled_quantity
    if remaining <= tolerance: remaining = 0.0

    return BacktestPosition(
        position.direction,
        remaining,
        position.average_entry_price if remaining else 0.0,
        position.realized_pnl_gross + realized,
        position.fees_paid + fee_amount(fill.filled_notional, fee_bps)
    )

def unrealized_pnl(position: BacktestPosition, mark_price: float) -> float:
    if not isfinite(mark_price) or mark_price <= 0: raise ValueError("mark_price must be positive and finite")
    if position.is_flat: return 0.0

    sign = 1 if position.direction == SignalDirection.LONG else -1
    return sign * (mark_price - position.average_entry_price) * position.quantity

def position_notional(position: BacktestPosition, mark_price: float) -> float:
    if not isfinite(mark_price) or mark_price <= 0: raise ValueError("mark_price must be positive and finite")
    return position.quantity * mark_price

def total_pnl(position: BacktestPosition, mark_price: float) -> float:
    return position.realized_pnl_gross + unrealized_pnl(position, mark_price) - position.fees_paid