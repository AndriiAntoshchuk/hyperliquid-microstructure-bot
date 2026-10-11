import pytest

from hlbot.backtest.latency import ExecutionLatency
from hlbot.strategy.engine import StrategyAction

def test_default_latency_is_zero():
    latency = ExecutionLatency()

    assert latency.seconds_for(StrategyAction.ENTER) == 0
    assert latency.seconds_for(StrategyAction.SCALE_IN) == 0
    assert latency.seconds_for(StrategyAction.EXIT) == 0

def test_latency_can_differ_by_action():
    latency = ExecutionLatency(
        entry_ms=100,
        scale_in_ms=200,
        exit_ms=50
    )

    assert latency.milliseconds_for(StrategyAction.ENTER) == pytest.approx(100)
    assert latency.milliseconds_for(StrategyAction.SCALE_IN) == pytest.approx(200)
    assert latency.milliseconds_for(StrategyAction.EXIT) == pytest.approx(50)

def test_latency_converts_to_seconds():
    latency = ExecutionLatency(entry_ms=250)

    assert latency.seconds_for(StrategyAction.ENTER) == pytest.approx(0.25)

def test_arrival_timestamp():
    latency = ExecutionLatency(entry_ms=350)

    assert latency.arrival_ts(
        1000,
        StrategyAction.ENTER
    ) == pytest.approx(1000.35)

def test_constant_latency_factory():
    latency = ExecutionLatency.constant(125)

    assert latency.entry_ms == pytest.approx(125)
    assert latency.scale_in_ms == pytest.approx(125)
    assert latency.exit_ms == pytest.approx(125)

def test_negative_latency_is_rejected():
    with pytest.raises(ValueError):
        ExecutionLatency(entry_ms=-1)

def test_hold_has_no_execution_latency():
    latency = ExecutionLatency()

    with pytest.raises(ValueError):
        latency.seconds_for(StrategyAction.HOLD)