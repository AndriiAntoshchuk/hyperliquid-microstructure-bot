from dataclasses import dataclass
from enum import Enum
from math import isfinite

from hlbot.strategy.signal import SignalDecision, SignalDirection
from hlbot.strategy.specification import StrategySpec, next_order_notional

class OrderIntentType(Enum):
    INITIAL_ENTRY = "initial_entry"
    SCALE_IN = "scale_in"

@dataclass(frozen=True)
class OrderIntent:
    direction: SignalDirection
    notional: float
    intent_type: OrderIntentType
    scale_index: int
    signal_strength: float
    reason: str = ""

    def __post_init__(self):
        if self.direction == SignalDirection.NONE:
            raise ValueError("order intent direction cannot be NONE")

        if not isfinite(self.notional) or self.notional <= 0:
            raise ValueError("notional must be positive and finite")

        if self.scale_index < 0:
            raise ValueError("scale_index cannot be negative")

        if self.intent_type == OrderIntentType.INITIAL_ENTRY and self.scale_index != 0:
            raise ValueError("initial entry must use scale_index 0")

        if self.intent_type == OrderIntentType.SCALE_IN and self.scale_index == 0:
            raise ValueError("scale-in must use scale_index greater than 0")

        if not isfinite(self.signal_strength) or not 0 <= self.signal_strength <= 1:
            raise ValueError("signal_strength must be between 0 and 1")

def build_order_intent(
    spec: StrategySpec,
    signal: SignalDecision,
    current_position_notional: float,
    scale_index: int
) -> OrderIntent | None:
    if scale_index < 0:
        raise ValueError("scale_index cannot be negative")

    if signal.direction == SignalDirection.NONE:
        return None

    notional = next_order_notional(
        spec,
        current_position_notional=current_position_notional,
        scale_index=scale_index
    )

    if notional <= 0:
        return None

    intent_type = (
        OrderIntentType.INITIAL_ENTRY
        if scale_index == 0
        else OrderIntentType.SCALE_IN
    )

    return OrderIntent(
        direction=signal.direction,
        notional=notional,
        intent_type=intent_type,
        scale_index=scale_index,
        signal_strength=signal.strength,
        reason=signal.reason
    )