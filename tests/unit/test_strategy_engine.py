import pytest

from hlbot.strategy.engine import StrategyAction, StrategyEngine, StrategyPosition
from hlbot.strategy.rules import ExitReason
from hlbot.strategy.signal import MarketState, NoSignalModel, SignalDecision, SignalDirection
from hlbot.strategy.specification import StrategySpec

class FixedSignalModel:
    def __init__(self, direction: SignalDirection, strength: float = 0.8):
        self.direction = direction
        self.strength = strength

    def evaluate(self, state: MarketState) -> SignalDecision:
        return SignalDecision(
            direction=self.direction,
            strength=self.strength,
            reason="fixed test signal"
        )

def make_spec(**kwargs) -> StrategySpec:
    values = {
        "base_order_notional": 1000,
        "max_position_notional": 5000,
        "max_scale_ins": 4
    }

    values.update(kwargs)
    return StrategySpec(**values)

def make_state(
    timestamp: float = 100,
    mid_price: float = 100,
    spread_bps: float = 2
) -> MarketState:
    return MarketState(
        timestamp=timestamp,
        mid_price=mid_price,
        spread_bps=spread_bps,
        imbalance_1=0,
        imbalance_5=0,
        weighted_imbalance_5=0,
        microprice_deviation_bps=0,
        trade_flow_5s=0,
        volatility_10s=0,
        bid_liquidity_10bps=1000,
        ask_liquidity_10bps=1000,
        return_5s=0,
        return_30s=0
    )

def make_position(**kwargs) -> StrategyPosition:
    values = {
        "direction": SignalDirection.LONG,
        "entry_price": 100,
        "entry_ts": 0,
        "current_notional": 1000,
        "scale_ins_used": 0
    }

    values.update(kwargs)
    return StrategyPosition(**values)

def test_flat_no_signal_holds():
    engine = StrategyEngine(make_spec(), NoSignalModel())

    decision = engine.evaluate(make_state())

    assert decision.action == StrategyAction.HOLD
    assert decision.order_intent is None

def test_flat_long_signal_enters():
    engine = StrategyEngine(
        make_spec(),
        FixedSignalModel(SignalDirection.LONG)
    )

    decision = engine.evaluate(make_state())

    assert decision.action == StrategyAction.ENTER
    assert decision.order_intent is not None
    assert decision.order_intent.direction == SignalDirection.LONG
    assert decision.order_intent.notional == 1000

def test_spread_filter_blocks_entry():
    engine = StrategyEngine(
        make_spec(max_spread_bps=5),
        FixedSignalModel(SignalDirection.LONG)
    )

    decision = engine.evaluate(make_state(spread_bps=6))

    assert decision.action == StrategyAction.HOLD
    assert decision.raw_signal.direction == SignalDirection.LONG
    assert decision.effective_signal.direction == SignalDirection.NONE

def test_same_direction_signal_scales_in():
    engine = StrategyEngine(
        make_spec(),
        FixedSignalModel(SignalDirection.LONG)
    )

    decision = engine.evaluate(
        make_state(),
        make_position()
    )

    assert decision.action == StrategyAction.SCALE_IN
    assert decision.order_intent is not None
    assert decision.order_intent.scale_index == 1
    assert decision.order_intent.notional == 1000

def test_opposite_signal_holds():
    engine = StrategyEngine(
        make_spec(),
        FixedSignalModel(SignalDirection.SHORT)
    )

    decision = engine.evaluate(
        make_state(),
        make_position()
    )

    assert decision.action == StrategyAction.HOLD
    assert decision.order_intent is None

def test_stop_loss_has_priority_over_scale_in():
    engine = StrategyEngine(
        make_spec(stop_loss_pct=2),
        FixedSignalModel(SignalDirection.LONG)
    )

    decision = engine.evaluate(
        make_state(timestamp=10, mid_price=97),
        make_position()
    )

    assert decision.action == StrategyAction.EXIT
    assert decision.exit_decision is not None
    assert decision.exit_decision.reason == ExitReason.STOP_LOSS
    assert decision.order_intent is None

def test_take_profit_exit():
    engine = StrategyEngine(
        make_spec(take_profit_pct=3),
        FixedSignalModel(SignalDirection.LONG)
    )

    decision = engine.evaluate(
        make_state(timestamp=10, mid_price=104),
        make_position()
    )

    assert decision.action == StrategyAction.EXIT
    assert decision.exit_decision is not None
    assert decision.exit_decision.reason == ExitReason.TAKE_PROFIT

def test_scale_limit_holds():
    engine = StrategyEngine(
        make_spec(),
        FixedSignalModel(SignalDirection.LONG)
    )

    decision = engine.evaluate(
        make_state(),
        make_position(
            current_notional=4000,
            scale_ins_used=4
        )
    )

    assert decision.action == StrategyAction.HOLD
    assert decision.order_intent is None

def test_invalid_strategy_position():
    with pytest.raises(ValueError):
        StrategyPosition(
            direction=SignalDirection.NONE,
            entry_price=100,
            entry_ts=0,
            current_notional=1000,
            scale_ins_used=0
        )