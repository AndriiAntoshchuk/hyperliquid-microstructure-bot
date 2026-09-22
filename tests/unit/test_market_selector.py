from dataclasses import replace

import pytest

from hlbot.features.market_activity_window import RollingMarketActivity
from hlbot.selection.market_selector import MarketSelector, MarketSelectorConfig

def activity(
    coin,
    volume=100,
    acceleration=1,
    oi=0.01,
    price=0.01,
    active=True,
    warm=True,
    day_volume=20_000_000,
    rv5=0.005
):
    return RollingMarketActivity(
        ts=100,
        dex="main",
        coin=coin,
        active=active,
        day_notional_volume=day_volume,
        volume_1m=volume / 5,
        volume_5m=volume,
        volume_15m=volume * 3,
        volume_acceleration_5m=acceleration,
        oi_notional_return_5m=oi,
        price_return_5m=price,
        warm=warm,
        realized_volatility_5m=rv5,
        realized_volatility_15m=None if rv5 is None else rv5 * 2
    )

def test_high_activity_market_ranks_first():
    selector = MarketSelector()
    result = selector.select((
        activity("A", 100, 1, 0.01, 0.01),
        activity("B", 500, 3, 0.05, 0.04),
        activity("C", 200, 1.5, 0.02, 0.02)
    ))

    assert result[0].coin == "B"
    assert result[0].score == pytest.approx(1)

def test_inactive_market_is_excluded():
    result = MarketSelector().select((
        activity("A"),
        activity("B", volume=1000, active=False)
    ))

    assert [row.coin for row in result] == ["A"]

def test_zero_volume_market_is_excluded():
    result = MarketSelector().select((
        activity("A"),
        activity("B", volume=0)
    ))

    assert [row.coin for row in result] == ["A"]

def test_cold_start_market_can_rank_without_acceleration():
    selector = MarketSelector()
    cold = activity("NEW", 1000, None, 0.05, 0.05, warm=False)
    old = activity("OLD", 100, 1, 0.01, 0.01)

    result = selector.select((cold, old))
    candidate = next(row for row in result if row.coin == "NEW")

    assert candidate.volume_acceleration_rank is None
    assert candidate.available_features == 3
    assert not candidate.warm

def test_absolute_oi_and_price_movement_are_ranked():
    result = MarketSelector().select((
        activity("A", oi=-0.10, price=-0.10),
        activity("B", oi=0.01, price=0.01)
    ))

    assert result[0].coin == "A"

def test_top_n_limits_candidates():
    selector = MarketSelector(MarketSelectorConfig(top_n=2))
    result = selector.select((
        activity("A", 100),
        activity("B", 200),
        activity("C", 300)
    ))

    assert len(result) == 2

def test_duplicate_market_rejected():
    selector = MarketSelector()

    with pytest.raises(ValueError, match="duplicate"):
        selector.select((activity("A"), activity("A")))

def test_invalid_config_rejected():
    with pytest.raises(ValueError):
        MarketSelectorConfig(top_n=0)

def test_market_below_volume_floor_is_excluded():
    assert MarketSelector().select((
        activity("LOW", day_volume=9_999_999),
    )) == ()

def test_market_at_volume_floor_is_eligible():
    assert MarketSelector().select((
        activity("OK", day_volume=10_000_000),
    ))

def test_volume_floor_is_configurable():
    selector = MarketSelector(MarketSelectorConfig(min_day_notional_volume=20_000_000))

    assert selector.select((
        activity("A", day_volume=15_000_000),
    )) == ()

def test_market_below_volatility_cost_hurdle_is_excluded():
    assert MarketSelector().select((
        activity("LOW", rv5=0.00199),
    )) == ()

def test_market_at_volatility_cost_hurdle_is_eligible():
    assert MarketSelector().select((
        activity("OK", rv5=0.002),
    ))

def test_missing_volatility_is_excluded():
    assert MarketSelector().select((
        activity("NONE", rv5=None),
    )) == ()

def test_cost_hurdle_is_configurable():
    selector = MarketSelector(MarketSelectorConfig(
        estimated_round_trip_cost=0.0015,
        min_volatility_cost_ratio=3
    ))

    assert selector.config.min_realized_volatility_5m == pytest.approx(0.0045)
    assert selector.select((activity("LOW", rv5=0.004),)) == ()
    assert selector.select((activity("OK", rv5=0.005),))

def test_zero_cost_disables_volatility_floor():
    selector = MarketSelector(MarketSelectorConfig(
        estimated_round_trip_cost=0,
        min_volatility_cost_ratio=0
    ))

    assert selector.select((activity("A", rv5=0),))