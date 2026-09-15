import pytest

from hlbot.strategy.order_intent import OrderIntentType
from hlbot.strategy.scale_in import ActivePositionSizing, build_scale_in_intent
from hlbot.strategy.signal import MarketState, SignalDecision, SignalDirection
from hlbot.strategy.specification import StrategySpec

def make_spec(**kwargs) -> StrategySpec:
    values = {
        "base_order_notional": 1000,
        "max_position_notional": 5000,
        "max_scale_ins": 4
    }

    values.update(kwargs)
    return StrategySpec(**values)

def make_state(spread_bps: float = 2) -> MarketState:
    return MarketState(
        timestamp=100,
        mid_price=100,
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

def make_signal(direction: SignalDirection = SignalDirection.LONG) -> SignalDecision:
    return SignalDecision(
        direction=direction,
        strength=0.8,
        reason="test"
    )

def test_first_scale_in():
    position = ActivePositionSizing(
        direction=SignalDirection.LONG,
        current_notional=1000,
        scale_ins_used=0
    )

    intent = build_scale_in_intent(
        make_spec(),
        position,
        make_state(),
        make_signal()
    )

    assert intent is not None
    assert intent.intent_type == OrderIntentType.SCALE_IN
    assert intent.scale_index == 1
    assert intent.notional == 1000

def test_later_scale_in():
    position = ActivePositionSizing(
        direction=SignalDirection.LONG,
        current_notional=3000,
        scale_ins_used=2
    )

    intent = build_scale_in_intent(
        make_spec(),
        position,
        make_state(),
        make_signal()
    )

    assert intent is not None
    assert intent.scale_index == 3
    assert intent.notional == 1000

def test_opposite_signal_does_not_scale_position():
    position = ActivePositionSizing(
        direction=SignalDirection.LONG,
        current_notional=1000,
        scale_ins_used=0
    )

    intent = build_scale_in_intent(
        make_spec(),
        position,
        make_state(),
        make_signal(SignalDirection.SHORT)
    )

    assert intent is None

def test_none_signal_does_not_scale_position():
    position = ActivePositionSizing(
        direction=SignalDirection.LONG,
        current_notional=1000,
        scale_ins_used=0
    )

    signal = SignalDecision(
        direction=SignalDirection.NONE,
        strength=0
    )

    assert build_scale_in_intent(
        make_spec(),
        position,
        make_state(),
        signal
    ) is None

def test_spread_filter_blocks_scale_in():
    position = ActivePositionSizing(
        direction=SignalDirection.LONG,
        current_notional=1000,
        scale_ins_used=0
    )

    intent = build_scale_in_intent(
        make_spec(max_spread_bps=5),
        position,
        make_state(spread_bps=6),
        make_signal()
    )

    assert intent is None

def test_position_cap_reduces_scale_order():
    position = ActivePositionSizing(
        direction=SignalDirection.LONG,
        current_notional=4500,
        scale_ins_used=3
    )

    intent = build_scale_in_intent(
        make_spec(),
        position,
        make_state(),
        make_signal()
    )

    assert intent is not None
    assert intent.notional == 500
    assert intent.scale_index == 4

def test_scale_limit_blocks_additional_order():
    position = ActivePositionSizing(
        direction=SignalDirection.LONG,
        current_notional=4000,
        scale_ins_used=4
    )

    assert build_scale_in_intent(
        make_spec(),
        position,
        make_state(),
        make_signal()
    ) is None

def test_invalid_active_position():
    with pytest.raises(ValueError):
        ActivePositionSizing(
            direction=SignalDirection.NONE,
            current_notional=1000,
            scale_ins_used=0
        )

    with pytest.raises(ValueError):
        ActivePositionSizing(
            direction=SignalDirection.LONG,
            current_notional=0,
            scale_ins_used=0
        )