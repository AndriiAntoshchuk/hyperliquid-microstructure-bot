import pytest

from hlbot.strategy.order_intent import OrderIntentType, build_order_intent
from hlbot.strategy.signal import SignalDecision, SignalDirection
from hlbot.strategy.specification import StrategySpec

def make_spec() -> StrategySpec:
    return StrategySpec(
        base_order_notional=1000,
        max_position_notional=5000,
        max_scale_ins=4
    )

def make_signal(direction: SignalDirection = SignalDirection.LONG) -> SignalDecision:
    return SignalDecision(
        direction=direction,
        strength=0.8,
        reason="test signal"
    )

def test_initial_long_order_intent():
    intent = build_order_intent(
        make_spec(),
        make_signal(),
        current_position_notional=0,
        scale_index=0
    )

    assert intent is not None
    assert intent.direction == SignalDirection.LONG
    assert intent.notional == 1000
    assert intent.intent_type == OrderIntentType.INITIAL_ENTRY
    assert intent.scale_index == 0
    assert intent.signal_strength == 0.8
    assert intent.reason == "test signal"

def test_initial_short_order_intent():
    intent = build_order_intent(
        make_spec(),
        make_signal(SignalDirection.SHORT),
        current_position_notional=0,
        scale_index=0
    )

    assert intent is not None
    assert intent.direction == SignalDirection.SHORT
    assert intent.intent_type == OrderIntentType.INITIAL_ENTRY

def test_scale_in_order_intent():
    intent = build_order_intent(
        make_spec(),
        make_signal(),
        current_position_notional=1000,
        scale_index=1
    )

    assert intent is not None
    assert intent.notional == 1000
    assert intent.intent_type == OrderIntentType.SCALE_IN
    assert intent.scale_index == 1

def test_none_signal_produces_no_order():
    signal = SignalDecision(
        direction=SignalDirection.NONE,
        strength=0
    )

    intent = build_order_intent(
        make_spec(),
        signal,
        current_position_notional=0,
        scale_index=0
    )

    assert intent is None

def test_order_is_capped_by_remaining_capacity():
    intent = build_order_intent(
        make_spec(),
        make_signal(),
        current_position_notional=4500,
        scale_index=4
    )

    assert intent is not None
    assert intent.notional == 500

def test_no_order_after_position_cap_or_scale_limit():
    spec = make_spec()

    assert build_order_intent(
        spec,
        make_signal(),
        current_position_notional=5000,
        scale_index=4
    ) is None

    assert build_order_intent(
        spec,
        make_signal(),
        current_position_notional=0,
        scale_index=5
    ) is None

def test_negative_scale_index_is_invalid():
    with pytest.raises(ValueError):
        build_order_intent(
            make_spec(),
            make_signal(),
            current_position_notional=0,
            scale_index=-1
        )