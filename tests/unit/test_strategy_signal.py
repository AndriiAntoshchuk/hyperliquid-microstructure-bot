import math

import pytest

from hlbot.strategy.signal import MarketState, NoSignalModel, SignalDecision, SignalDirection

def make_state() -> MarketState:
    return MarketState(
        timestamp=1000,
        mid_price=0.6,
        spread_bps=2,
        imbalance_1=0.2,
        imbalance_5=0.1,
        weighted_imbalance_5=0.15,
        microprice_deviation_bps=0.5,
        trade_flow_5s=0.3,
        volatility_10s=0.001,
        bid_liquidity_10bps=5000,
        ask_liquidity_10bps=4500,
        return_5s=0.001,
        return_30s=-0.002
    )

def test_market_state():
    state = make_state()

    assert state.mid_price == 0.6
    assert state.imbalance_5 == 0.1
    assert state.trade_flow_5s == 0.3

def test_signal_directions():
    assert SignalDirection.LONG.value == "long"
    assert SignalDirection.SHORT.value == "short"
    assert SignalDirection.NONE.value == "none"

def test_signal_decision():
    decision = SignalDecision(
        direction=SignalDirection.LONG,
        strength=0.75,
        reason="test"
    )

    assert decision.direction == SignalDirection.LONG
    assert decision.strength == 0.75

def test_none_signal_requires_zero_strength():
    with pytest.raises(ValueError):
        SignalDecision(
            direction=SignalDirection.NONE,
            strength=0.5
        )

def test_invalid_market_state():
    values = vars(make_state()).copy()
    values["mid_price"] = -1

    with pytest.raises(ValueError):
        MarketState(**values)

    values = vars(make_state()).copy()
    values["spread_bps"] = -1

    with pytest.raises(ValueError):
        MarketState(**values)

    values = vars(make_state()).copy()
    values["return_5s"] = math.nan

    with pytest.raises(ValueError):
        MarketState(**values)

def test_no_signal_model():
    model = NoSignalModel()
    decision = model.evaluate(make_state())

    assert decision.direction == SignalDirection.NONE
    assert decision.strength == 0
    assert decision.reason == "No calibrated signal model"