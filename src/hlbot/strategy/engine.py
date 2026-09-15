from dataclasses import dataclass
from enum import Enum
from math import isfinite

from hlbot.strategy.order_intent import OrderIntent, build_order_intent
from hlbot.strategy.rules import ExitDecision, PositionState, apply_entry_filters, evaluate_exit
from hlbot.strategy.scale_in import ActivePositionSizing, build_scale_in_intent
from hlbot.strategy.signal import MarketState, SignalDecision, SignalDirection, SignalModel
from hlbot.strategy.specification import StrategySpec

class StrategyAction(Enum):
    HOLD = "hold"
    ENTER = "enter"
    SCALE_IN = "scale_in"
    EXIT = "exit"

@dataclass(frozen=True)
class StrategyPosition:
    direction: SignalDirection
    entry_price: float
    entry_ts: float
    current_notional: float
    scale_ins_used: int

    def __post_init__(self):
        if self.direction == SignalDirection.NONE:
            raise ValueError("position direction cannot be NONE")

        if not isfinite(self.entry_price) or self.entry_price <= 0:
            raise ValueError("entry_price must be positive and finite")

        if not isfinite(self.entry_ts):
            raise ValueError("entry_ts must be finite")

        if not isfinite(self.current_notional) or self.current_notional <= 0:
            raise ValueError("current_notional must be positive and finite")

        if self.scale_ins_used < 0:
            raise ValueError("scale_ins_used cannot be negative")

    def exit_state(self) -> PositionState:
        return PositionState(
            direction=self.direction,
            entry_price=self.entry_price,
            entry_ts=self.entry_ts
        )

    def sizing_state(self) -> ActivePositionSizing:
        return ActivePositionSizing(
            direction=self.direction,
            current_notional=self.current_notional,
            scale_ins_used=self.scale_ins_used
        )

@dataclass(frozen=True)
class StrategyDecision:
    action: StrategyAction
    raw_signal: SignalDecision
    effective_signal: SignalDecision
    order_intent: OrderIntent | None = None
    exit_decision: ExitDecision | None = None

    def __post_init__(self):
        if self.action in {StrategyAction.ENTER, StrategyAction.SCALE_IN}:
            if self.order_intent is None:
                raise ValueError("order action requires order_intent")

            if self.exit_decision is not None:
                raise ValueError("order action cannot contain exit_decision")

        if self.action == StrategyAction.EXIT:
            if self.exit_decision is None or not self.exit_decision.should_exit:
                raise ValueError("exit action requires active exit_decision")

            if self.order_intent is not None:
                raise ValueError("exit action cannot contain order_intent")

        if self.action == StrategyAction.HOLD and self.order_intent is not None:
            raise ValueError("hold action cannot contain order_intent")

class StrategyEngine:
    def __init__(self, spec: StrategySpec, signal_model: SignalModel):
        self.spec = spec
        self.signal_model = signal_model

    def evaluate(self, state: MarketState, position: StrategyPosition | None = None) -> StrategyDecision:
        raw_signal = self.signal_model.evaluate(state)
        effective_signal = apply_entry_filters(self.spec, state, raw_signal)

        if position is None:
            return self._evaluate_flat(raw_signal, effective_signal)

        return self._evaluate_position(state, position, raw_signal, effective_signal)

    def _evaluate_flat(
        self,
        raw_signal: SignalDecision,
        effective_signal: SignalDecision
    ) -> StrategyDecision:
        intent = build_order_intent(
            spec=self.spec,
            signal=effective_signal,
            current_position_notional=0,
            scale_index=0
        )

        if intent is None:
            return StrategyDecision(
                action=StrategyAction.HOLD,
                raw_signal=raw_signal,
                effective_signal=effective_signal
            )

        return StrategyDecision(
            action=StrategyAction.ENTER,
            raw_signal=raw_signal,
            effective_signal=effective_signal,
            order_intent=intent
        )

    def _evaluate_position(
        self,
        state: MarketState,
        position: StrategyPosition,
        raw_signal: SignalDecision,
        effective_signal: SignalDecision
    ) -> StrategyDecision:
        exit_decision = evaluate_exit(
            self.spec,
            position.exit_state(),
            state
        )

        if exit_decision.should_exit:
            return StrategyDecision(
                action=StrategyAction.EXIT,
                raw_signal=raw_signal,
                effective_signal=effective_signal,
                exit_decision=exit_decision
            )

        intent = build_scale_in_intent(
            spec=self.spec,
            position=position.sizing_state(),
            state=state,
            signal=effective_signal
        )

        if intent is None:
            return StrategyDecision(
                action=StrategyAction.HOLD,
                raw_signal=raw_signal,
                effective_signal=effective_signal,
                exit_decision=exit_decision
            )

        return StrategyDecision(
            action=StrategyAction.SCALE_IN,
            raw_signal=raw_signal,
            effective_signal=effective_signal,
            order_intent=intent
        )