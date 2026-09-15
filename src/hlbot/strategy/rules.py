from dataclasses import dataclass
from enum import Enum
from math import isfinite

from hlbot.strategy.signal import MarketState, SignalDecision, SignalDirection
from hlbot.strategy.specification import StrategySpec

class ExitReason(Enum):
    NONE = "none"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    MAX_HOLDING_TIME = "max_holding_time"

@dataclass(frozen=True)
class PositionState:
    direction: SignalDirection
    entry_price: float
    entry_ts: float

    def __post_init__(self):
        if self.direction == SignalDirection.NONE:
            raise ValueError("position direction cannot be NONE")

        if not isfinite(self.entry_price) or self.entry_price <= 0:
            raise ValueError("entry_price must be positive and finite")

        if not isfinite(self.entry_ts):
            raise ValueError("entry_ts must be finite")

@dataclass(frozen=True)
class ExitDecision:
    should_exit: bool
    reason: ExitReason
    return_pct: float

    def __post_init__(self):
        if not isfinite(self.return_pct):
            raise ValueError("return_pct must be finite")

        if not self.should_exit and self.reason != ExitReason.NONE:
            raise ValueError("non-exit decision must use ExitReason.NONE")

def position_return_pct(position: PositionState, current_price: float) -> float:
    if not isfinite(current_price) or current_price <= 0:
        raise ValueError("current_price must be positive and finite")

    raw_return = current_price / position.entry_price - 1

    if position.direction == SignalDirection.LONG:
        return raw_return * 100

    return -raw_return * 100

def apply_entry_filters(spec: StrategySpec, state: MarketState, signal: SignalDecision) -> SignalDecision:
    if signal.direction == SignalDirection.NONE:
        return signal

    if spec.max_spread_bps is not None and state.spread_bps > spec.max_spread_bps:
        return SignalDecision(
            direction=SignalDirection.NONE,
            strength=0.0,
            reason="Spread exceeds strategy limit"
        )

    return signal

def evaluate_exit(spec: StrategySpec, position: PositionState, state: MarketState) -> ExitDecision:
    return_pct = position_return_pct(position, state.mid_price)

    if spec.stop_loss_pct is not None and return_pct <= -spec.stop_loss_pct:
        return ExitDecision(
            should_exit=True,
            reason=ExitReason.STOP_LOSS,
            return_pct=return_pct
        )

    if spec.take_profit_pct is not None and return_pct >= spec.take_profit_pct:
        return ExitDecision(
            should_exit=True,
            reason=ExitReason.TAKE_PROFIT,
            return_pct=return_pct
        )

    holding_seconds = state.timestamp - position.entry_ts

    if holding_seconds < 0:
        raise ValueError("market state cannot precede position entry")

    if spec.max_holding_seconds is not None and holding_seconds >= spec.max_holding_seconds:
        return ExitDecision(
            should_exit=True,
            reason=ExitReason.MAX_HOLDING_TIME,
            return_pct=return_pct
        )

    return ExitDecision(
        should_exit=False,
        reason=ExitReason.NONE,
        return_pct=return_pct
    )