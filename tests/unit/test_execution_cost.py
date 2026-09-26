import pytest

from hlbot.features.execution_cost import execution_cost
from hlbot.features.execution_quality import ExecutionQuality

def quality():
    return ExecutionQuality(
        coin="PONS",
        snapshots=100,
        buy_full_rate=0.98,
        sell_full_rate=0.96,
        spread_p50_bps=2,
        spread_p90_bps=3,
        buy_slippage_p50_bps=1,
        buy_slippage_p90_bps=2,
        sell_slippage_p50_bps=1,
        sell_slippage_p90_bps=2.5,
        round_trip_p90_bps=4.5,
        two_sided_depth_p10=1000,
        two_sided_depth_p50=2000
    )

def test_execution_cost():
    result = execution_cost(
        500,
        quality(),
        fee_bps_per_side=2,
        latency_buffer_bps=1
    )

    assert result.fill_rate == pytest.approx(0.96)
    assert result.spread_bps == pytest.approx(3)
    assert result.impact_bps == pytest.approx(4.5)
    assert result.fees_bps == pytest.approx(4)
    assert result.total_bps == pytest.approx(12.5)

def test_missing_impact_returns_none():
    q = quality()
    q = ExecutionQuality(
        **{**q.__dict__, "round_trip_p90_bps": None}
    )

    assert execution_cost(500, q) is None