import pytest

from hlbot.strategy.rules import ExitReason, PositionState, apply_entry_filters, evaluate_exit, position_return_pct
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

def make_state(timestamp: float = 100, mid_price: float = 100, spread_bps: float = 2) -> MarketState:
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

def test_long_position_return():
    position = PositionState(
        direction=SignalDirection.LONG,
        entry_price=100,
        entry_ts=0
    )

    assert position_return_pct(position, 105) == pytest.approx(5)
    assert position_return_pct(position, 95) == pytest.approx(-5)

def test_short_position_return():
    position = PositionState(
        direction=SignalDirection.SHORT,
        entry_price=100,
        entry_ts=0
    )

    assert position_return_pct(position, 95) == pytest.approx(5)
    assert position_return_pct(position, 105) == pytest.approx(-5)

def test_spread_filter_rejects_entry():
    spec = make_spec(max_spread_bps=5)
    state = make_state(spread_bps=6)
    signal = SignalDecision(
        direction=SignalDirection.LONG,
        strength=0.8,
        reason="test"
    )

    decision = apply_entry_filters(spec, state, signal)

    assert decision.direction == SignalDirection.NONE
    assert decision.strength == 0

def test_spread_filter_allows_entry():
    spec = make_spec(max_spread_bps=5)
    state = make_state(spread_bps=4)
    signal = SignalDecision(
        direction=SignalDirection.LONG,
        strength=0.8,
        reason="test"
    )

    assert apply_entry_filters(spec, state, signal) == signal

def test_stop_loss_exit():
    spec = make_spec(stop_loss_pct=2)
    position = PositionState(
        direction=SignalDirection.LONG,
        entry_price=100,
        entry_ts=0
    )

    decision = evaluate_exit(spec, position, make_state(timestamp=10, mid_price=97))

    assert decision.should_exit
    assert decision.reason == ExitReason.STOP_LOSS
    assert decision.return_pct == pytest.approx(-3)

def test_take_profit_exit():
    spec = make_spec(take_profit_pct=3)
    position = PositionState(
        direction=SignalDirection.LONG,
        entry_price=100,
        entry_ts=0
    )

    decision = evaluate_exit(spec, position, make_state(timestamp=10, mid_price=104))

    assert decision.should_exit
    assert decision.reason == ExitReason.TAKE_PROFIT
    assert decision.return_pct == pytest.approx(4)

def test_max_holding_time_exit():
    spec = make_spec(max_holding_seconds=30)
    position = PositionState(
        direction=SignalDirection.LONG,
        entry_price=100,
        entry_ts=100
    )

    decision = evaluate_exit(spec, position, make_state(timestamp=130, mid_price=100))

    assert decision.should_exit
    assert decision.reason == ExitReason.MAX_HOLDING_TIME

def test_no_exit():
    spec = make_spec(
        stop_loss_pct=5,
        take_profit_pct=5,
        max_holding_seconds=60
    )

    position = PositionState(
        direction=SignalDirection.LONG,
        entry_price=100,
        entry_ts=100
    )

    decision = evaluate_exit(spec, position, make_state(timestamp=120, mid_price=101))

    assert not decision.should_exit
    assert decision.reason == ExitReason.NONE

def test_position_cannot_have_none_direction():
    with pytest.raises(ValueError):
        PositionState(
            direction=SignalDirection.NONE,
            entry_price=100,
            entry_ts=0
        )