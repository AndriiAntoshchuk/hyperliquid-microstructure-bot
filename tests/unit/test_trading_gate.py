import pytest

from hlbot.features.execution_quality import ExecutionQuality
from hlbot.selection.trading_gate import best_tradeable_notional

def point(notional, full=1, spread=2, impact=3):
    quality = ExecutionQuality(
        coin="PONS",
        snapshots=100,
        buy_full_rate=full,
        sell_full_rate=full,
        spread_p50_bps=spread,
        spread_p90_bps=spread,
        buy_slippage_p50_bps=1,
        buy_slippage_p90_bps=1,
        sell_slippage_p50_bps=1,
        sell_slippage_p90_bps=2,
        round_trip_p90_bps=impact,
        two_sided_depth_p10=1000,
        two_sided_depth_p50=2000
    )

    return {
        "notional": notional,
        "quality": quality.__dict__
    }

def test_chooses_largest_passing_notional():
    result = best_tradeable_notional(
        (
            point(100),
            point(500),
            point(1000, full=0.90)
        ),
        realized_volatility=0.004,
        fee_bps_per_side=5
    )

    assert result.notional == 500
    assert result.cost_bps == pytest.approx(15)
    assert result.movement_cost_ratio == pytest.approx(40 / 15)

def test_rejects_insufficient_movement():
    result = best_tradeable_notional(
        (point(100),),
        realized_volatility=0.001,
        fee_bps_per_side=5
    )

    assert result is None