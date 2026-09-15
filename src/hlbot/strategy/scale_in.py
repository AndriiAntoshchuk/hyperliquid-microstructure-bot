from dataclasses import dataclass
from math import isfinite

from hlbot.strategy.order_intent import OrderIntent, build_order_intent
from hlbot.strategy.rules import apply_entry_filters
from hlbot.strategy.signal import MarketState, SignalDecision, SignalDirection
from hlbot.strategy.specification import StrategySpec

@dataclass(frozen=True)
class ActivePositionSizing:
    direction: SignalDirection
    current_notional: float
    scale_ins_used: int

    def __post_init__(self):
        if self.direction == SignalDirection.NONE:
            raise ValueError("position direction cannot be NONE")

        if not isfinite(self.current_notional) or self.current_notional <= 0:
            raise ValueError("current_notional must be positive and finite")

        if self.scale_ins_used < 0:
            raise ValueError("scale_ins_used cannot be negative")

    @property
    def next_scale_index(self) -> int:
        return self.scale_ins_used + 1

def build_scale_in_intent(
    spec: StrategySpec,
    position: ActivePositionSizing,
    state: MarketState,
    signal: SignalDecision
) -> OrderIntent | None:
    filtered_signal = apply_entry_filters(spec, state, signal)

    if filtered_signal.direction == SignalDirection.NONE:
        return None

    if filtered_signal.direction != position.direction:
        return None

    return build_order_intent(
        spec=spec,
        signal=filtered_signal,
        current_position_notional=position.current_notional,
        scale_index=position.next_scale_index
    )