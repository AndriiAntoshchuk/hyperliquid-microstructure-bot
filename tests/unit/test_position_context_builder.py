from dataclasses import replace

import pytest

from hlbot.strategy.engine import StrategyPosition
from hlbot.strategy.position_context import (
    PositionContextBuilder,
    imbalance,
    signed_return_bps,
)
from hlbot.strategy.signal import MarketState, SignalDirection


def state(ts, price=100, bid=60, ask=40):
    return MarketState(
        timestamp=ts, mid_price=price, spread_bps=5, imbalance_1=0.1,
        imbalance_5=0.2, weighted_imbalance_5=0.3, microprice_deviation_bps=2,
        trade_flow_5s=0.4, volatility_10s=0.001,
        bid_liquidity_10bps=bid, ask_liquidity_10bps=ask,
        return_5s=0.002, return_30s=0.004,
        bid_visible_notional_5=300, ask_visible_notional_5=100,
    )


def pos(direction=SignalDirection.LONG, entry_price=100, ts=0, notional=50):
    return StrategyPosition(direction, entry_price, ts, notional, 1)


def test_helpers_and_validation():
    assert imbalance(0, 0) == 0
    assert imbalance(60, 40) == 0.2
    assert signed_return_bps(110, 100, -1) == pytest.approx(-1000)
    with pytest.raises(ValueError, match="max_position_notional"):
        PositionContextBuilder().build(state(1), pos(), float("nan"))


def test_long_inventory_running_extrema_and_flat_reset():
    builder = PositionContextBuilder(max_gap_seconds=2)
    assert builder.build(state(1), None, 100) is None
    first = builder.build(state(2, 101), pos(ts=2), 100)
    assert first.holding_seconds == 0
    assert first.inventory_fraction == 0.5
    assert first.remaining_capacity_fraction == 0.5
    assert first.mfe_bps == pytest.approx(100)
    second = builder.build(state(3, 98), pos(ts=2), 100)
    assert second.mae_bps == pytest.approx(-200)
    assert second.mfe_bps == pytest.approx(100)
    assert second.aligned_microprice_bps == 2
    assert second.liquidity_imbalance == pytest.approx(0.2)
    assert builder.build(state(4), None, 100) is None
    fresh = builder.build(state(5, 100), pos(ts=5), 100)
    assert fresh.mfe_bps == 0 and fresh.mae_bps == 0


def test_short_direction_and_scale_in_avg_entry():
    builder = PositionContextBuilder()
    short = pos(SignalDirection.SHORT, entry_price=100, ts=1, notional=80)
    ctx = builder.build(state(2, 98), short, 100)
    assert ctx.avg_entry_return_bps == pytest.approx(200)
    assert ctx.aligned_imbalance_1 == -0.1
    assert ctx.return_5s_bps == -20
    new_cost_basis = replace(short, entry_price=99)
    ctx = builder.build(state(3, 101), new_cost_basis, 100)
    assert ctx.initial_entry_return_bps == pytest.approx(-100)
    assert ctx.avg_entry_return_bps == pytest.approx(-202.020202020202)
    assert ctx.mae_bps == pytest.approx(-100)


def test_lookback_windows_and_gap_invalidation():
    builder = PositionContextBuilder(max_gap_seconds=10)
    p = pos(ts=10)
    for ts in range(10, 321, 10):
        ctx = builder.build(state(ts, 100 + ts / 100), p, 100)
    assert ctx.return_60s_bps is not None
    assert ctx.return_120s_bps is not None
    assert ctx.return_300s_bps is not None
    assert ctx.weighted_change_30s == 0
    assert len(builder.states) <= 32

    gap_ctx = builder.build(state(400), p, 100)
    assert gap_ctx.return_60s_bps is None
    assert gap_ctx.weighted_change_5s is None
    with pytest.raises(ValueError, match="chronological"):
        builder.build(state(399), p, 100)
