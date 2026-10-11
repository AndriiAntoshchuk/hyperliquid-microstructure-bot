from dataclasses import dataclass, replace
from enum import Enum
from math import isfinite

from hlbot.strategy.liquidity_sizing import cap_notional
from hlbot.strategy.position_policy import PositionPolicy
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
        if self.direction == SignalDirection.NONE: raise ValueError("position direction cannot be NONE")
        if not isfinite(self.entry_price) or self.entry_price <= 0: raise ValueError("entry_price must be positive and finite")
        if not isfinite(self.entry_ts): raise ValueError("entry_ts must be finite")
        if not isfinite(self.current_notional) or self.current_notional <= 0: raise ValueError("current_notional must be positive and finite")
        if self.scale_ins_used < 0: raise ValueError("scale_ins_used cannot be negative")

    def exit_state(self) -> PositionState:
        return PositionState(self.direction, self.entry_price, self.entry_ts)

    def sizing_state(self) -> ActivePositionSizing:
        return ActivePositionSizing(self.direction, self.current_notional, self.scale_ins_used)

@dataclass(frozen=True)
class StrategyDecision:
    action: StrategyAction
    raw_signal: SignalDecision
    effective_signal: SignalDecision
    order_intent: OrderIntent | None = None
    exit_decision: ExitDecision | None = None

    def __post_init__(self):
        if self.action in {StrategyAction.ENTER, StrategyAction.SCALE_IN}:
            if self.order_intent is None: raise ValueError("order action requires order_intent")
            if self.exit_decision is not None: raise ValueError("order action cannot contain exit_decision")

        if self.action == StrategyAction.EXIT:
            if self.exit_decision is None or not self.exit_decision.should_exit:
                raise ValueError("exit action requires active exit_decision")
            if self.order_intent is not None: raise ValueError("exit action cannot contain order_intent")

        if self.action == StrategyAction.HOLD and self.order_intent is not None:
            raise ValueError("hold action cannot contain order_intent")

class StrategyEngine:
    def __init__(
        self,
        spec: StrategySpec,
        signal_model: SignalModel,
        position_policy: PositionPolicy | None = None
    ):
        self.spec = spec
        self.signal_model = signal_model
        self.position_policy = position_policy

    def evaluate(self, state: MarketState, position: StrategyPosition | None = None) -> StrategyDecision:
        raw_signal = self.signal_model.evaluate(state)
        effective_signal = apply_entry_filters(self.spec, state, raw_signal)

        if position is None: return self._evaluate_flat(state, raw_signal, effective_signal)
        return self._evaluate_position(state, position, raw_signal, effective_signal)

    def _apply_liquidity_cap(self, state: MarketState, intent: OrderIntent | None) -> OrderIntent | None:
        if intent is None or self.spec.max_visible_liquidity_fraction is None: return intent

        notional = cap_notional(
            intent.notional,
            state.bid_visible_notional_5,
            state.ask_visible_notional_5,
            self.spec.max_visible_liquidity_fraction
        )

        if notional <= 0: return None
        return replace(intent, notional=notional)

    def _evaluate_flat(
        self,
        state: MarketState,
        raw_signal: SignalDecision,
        effective_signal: SignalDecision
    ) -> StrategyDecision:
        intent = build_order_intent(self.spec, effective_signal, 0, 0)
        intent = self._apply_liquidity_cap(state, intent)

        if intent is None:
            return StrategyDecision(StrategyAction.HOLD, raw_signal, effective_signal)

        return StrategyDecision(StrategyAction.ENTER, raw_signal, effective_signal, order_intent=intent)

    def _evaluate_position(
        self,
        state: MarketState,
        position: StrategyPosition,
        raw_signal: SignalDecision,
        effective_signal: SignalDecision
    ) -> StrategyDecision:
        exit_decision = evaluate_exit(self.spec, position.exit_state(), state)

        exit_decision = evaluate_exit(self.spec, position.exit_state(), state)

        if exit_decision.should_exit:
            return StrategyDecision(
                StrategyAction.EXIT,
                raw_signal,
                effective_signal,
                exit_decision=exit_decision
            )

        if self.position_policy is not None:
            exit_decision = self.position_policy.evaluate(state, position.exit_state())

            if exit_decision.should_exit:
                return StrategyDecision(
                    StrategyAction.EXIT,
                    raw_signal,
                    effective_signal,
                    exit_decision=exit_decision
                )

        intent = build_scale_in_intent(self.spec, position.sizing_state(), state, effective_signal)
        intent = self._apply_liquidity_cap(state, intent)

        if intent is None:
            return StrategyDecision(StrategyAction.HOLD, raw_signal, effective_signal, exit_decision=exit_decision)

        return StrategyDecision(StrategyAction.SCALE_IN, raw_signal, effective_signal, order_intent=intent)