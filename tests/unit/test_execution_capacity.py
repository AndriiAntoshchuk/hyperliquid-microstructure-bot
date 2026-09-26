from unittest.mock import patch

from hlbot.features.execution_capacity import analyze_execution_capacity
from hlbot.features.execution_quality import ExecutionQuality

def quality(coin, full):
    return ExecutionQuality(
        coin=coin,
        snapshots=100,
        buy_full_rate=full,
        sell_full_rate=full,
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

def test_capacity_uses_largest_notional_above_fill_threshold():
    curve = (
        (100, quality("PONS", 1)),
        (500, quality("PONS", 0.98)),
        (1000, quality("PONS", 0.90))
    )

    with patch(
        "hlbot.features.execution_capacity.analyze_execution_curve",
        return_value=curve
    ) as analyzer:
        result = analyze_execution_capacity(
            "data",
            "PONS",
            10000,
            notionals=(100, 500, 1000)
        )

    assert result.max_notional == 500
    assert analyzer.call_count == 1

def test_capacity_none_when_all_fail():
    curve = (
        (100, quality("PONS", 0.90)),
        (500, quality("PONS", 0.90))
    )

    with patch(
        "hlbot.features.execution_capacity.analyze_execution_curve",
        return_value=curve
    ):
        result = analyze_execution_capacity(
            "data",
            "PONS",
            10000,
            notionals=(100, 500)
        )

    assert result.max_notional is None