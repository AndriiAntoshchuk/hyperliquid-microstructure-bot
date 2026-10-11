from unittest.mock import patch

from hlbot.features.execution_capacity import ExecutionCapacity
from hlbot.features.execution_profile import build_execution_profile
from hlbot.features.execution_quality import ExecutionQuality

def quality():
    return ExecutionQuality(
        coin="PONS",
        snapshots=100,
        buy_full_rate=1,
        sell_full_rate=1,
        spread_p50_bps=1,
        spread_p90_bps=2,
        buy_slippage_p50_bps=1,
        buy_slippage_p90_bps=2,
        sell_slippage_p50_bps=1,
        sell_slippage_p90_bps=2,
        round_trip_p90_bps=4,
        two_sided_depth_p10=1000,
        two_sided_depth_p50=2000
    )

def test_supported_ready_market_is_analyzed():
    capacity = ExecutionCapacity(
        "PONS",
        500,
        0.95,
        ((100, quality()), (500, quality()))
    )

    with patch(
        "hlbot.features.execution_profile.analyze_execution_capacity",
        return_value=capacity
    ) as analyzer:
        result = build_execution_profile(
            [{"dex": "main", "coin": "PONS", "rank": 1}],
            {"PONS": True},
            "data",
            10000
        )

    assert analyzer.call_count == 1
    assert result[0]["max_notional"] == 500
    assert len(result[0]["curve"]) == 2

def test_unsupported_market_is_not_analyzed():
    with patch(
        "hlbot.features.execution_profile.analyze_execution_capacity"
    ) as analyzer:
        result = build_execution_profile(
            [{"dex": "xyz", "coin": "SOXL", "rank": 1}],
            {"SOXL": True},
            "data",
            10000
        )

    assert analyzer.call_count == 0
    assert result[0]["curve"] == []