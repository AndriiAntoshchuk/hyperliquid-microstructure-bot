import pytest

from hlbot.data.universe_collector import UniverseMarket
from hlbot.features.market_activity import MarketActivityTracker, market_activity

def market(
    ts=100,
    coin="PONS",
    dex="main",
    volume=1000,
    oi=100,
    mark=10,
    mid=10,
    delisted=False
):
    return UniverseMarket(
        ts=ts,
        dex=dex,
        coin=coin,
        is_delisted=delisted,
        sz_decimals=3,
        max_leverage=5,
        day_notional_volume=volume,
        day_base_volume=100,
        open_interest=oi,
        funding=0.0001,
        premium=0.001,
        oracle_price=mark,
        mark_price=mark,
        mid_price=mid,
        prev_day_price=9
    )

def test_market_activity():
    previous = market()
    current = market(ts=160, volume=1300, oi=110, mark=11)

    activity = market_activity(previous, current)

    assert activity.elapsed_seconds == 60
    assert activity.day_volume_change == 300
    assert activity.day_volume_change_per_minute == 300
    assert activity.day_volume_return == pytest.approx(0.3)
    assert activity.open_interest_change == 10
    assert activity.open_interest_return == pytest.approx(0.1)
    assert activity.oi_notional == pytest.approx(1210)
    assert activity.oi_notional_change == pytest.approx(210)
    assert activity.oi_notional_return == pytest.approx(0.21)
    assert activity.price_return == pytest.approx(0.1)

def test_zero_baselines_return_none():
    previous = market(volume=0, oi=0, mark=0)
    current = market(ts=160)

    activity = market_activity(previous, current)

    assert activity.day_volume_return is None
    assert activity.open_interest_return is None
    assert activity.oi_notional_return is None
    assert activity.price_return is None

def test_market_identity_mismatch_rejected():
    with pytest.raises(ValueError, match="identity mismatch"):
        market_activity(market(), market(ts=160, coin="LIT"))

def test_non_increasing_timestamp_rejected():
    with pytest.raises(ValueError, match="timestamp"):
        market_activity(market(), market(ts=100))

def test_tracker_requires_two_snapshots():
    tracker = MarketActivityTracker()

    assert tracker.update((market(),)) == ()

    activities = tracker.update((market(ts=160, volume=1200),))

    assert len(activities) == 1
    assert activities[0].day_volume_change == 200

def test_tracker_handles_multiple_markets():
    tracker = MarketActivityTracker()
    tracker.update((market(coin="PONS"), market(coin="LIT")))

    activities = tracker.update((
        market(ts=160, coin="PONS", volume=1200),
        market(ts=160, coin="LIT", volume=1500)
    ))

    assert {activity.coin for activity in activities} == {"PONS", "LIT"}

def test_tracker_ignores_out_of_order_rows():
    tracker = MarketActivityTracker()
    tracker.update((market(ts=160),))

    assert tracker.update((market(ts=100),)) == ()
    
def test_tracker_skips_long_gap():
    tracker = MarketActivityTracker()
    tracker.update((market(ts=100, volume=1000),))

    assert tracker.update((market(ts=300, volume=5000),)) == ()

    activities = tracker.update((market(ts=360, volume=5100),))
    assert len(activities) == 1
    assert activities[0].day_volume_change == 100