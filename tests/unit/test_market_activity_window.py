import pytest

from hlbot.features.market_activity import MarketActivity
from hlbot.features.market_activity_window import MarketActivityWindow

def activity(ts, volume=100, oi=1000, oi_change=0, price_return=0, coin="PONS"):
    return MarketActivity(
        ts=ts,
        dex="main",
        coin=coin,
        active=True,
        elapsed_seconds=60,
        day_notional_volume=20_000_000,
        day_volume_change=volume,
        day_volume_return=None,
        open_interest_change=0,
        open_interest_return=None,
        oi_notional=oi,
        oi_notional_change=oi_change,
        oi_notional_return=None,
        price_return=price_return
    )

def warm_window(last_volume=100):
    window = MarketActivityWindow()
    result = None

    for minute in range(1, 36):
        volume = last_volume if minute > 30 else 100
        result = window.update((activity(minute * 60, volume=volume),))[0]

    return result

def test_requires_35_minutes_for_baseline():
    result = MarketActivityWindow().update((activity(60),))[0]

    assert not result.warm
    assert result.volume_acceleration_5m is None

def test_constant_activity_has_unit_acceleration():
    result = warm_window()

    assert result.warm
    assert result.volume_1m == 100
    assert result.volume_5m == 500
    assert result.volume_15m == 1500
    assert result.volume_acceleration_5m == pytest.approx(1)

def test_recent_volume_spike_is_detected():
    result = warm_window(300)

    assert result.volume_5m == 1500
    assert result.volume_acceleration_5m == pytest.approx(3)

def test_negative_volume_change_is_not_counted():
    result = MarketActivityWindow().update((activity(60, volume=-100),))[0]

    assert result.volume_1m == 0
    assert result.volume_5m == 0

def test_oi_notional_return():
    window = MarketActivityWindow()
    result = None

    for minute in range(1, 6):
        oi = 1000 + minute * 10
        result = window.update((activity(minute * 60, oi=oi, oi_change=10),))[0]

    assert result.oi_notional_return_5m == pytest.approx(0.05)

def test_price_return_is_compounded():
    window = MarketActivityWindow()
    result = None

    for minute in range(1, 6):
        result = window.update((activity(minute * 60, price_return=0.01),))[0]

    assert result.price_return_5m == pytest.approx(1.01 ** 5 - 1)

def test_realized_volatility_5m():
    window = MarketActivityWindow()
    result = None

    for minute in range(1, 6):
        result = window.update((activity(minute * 60, price_return=0.01),))[0]

    assert result.realized_volatility_5m == pytest.approx(0.01 * 5 ** 0.5)

def test_realized_volatility_15m():
    window = MarketActivityWindow()
    result = None

    for minute in range(1, 16):
        result = window.update((activity(minute * 60, price_return=0.01),))[0]

    assert result.realized_volatility_15m == pytest.approx(0.01 * 15 ** 0.5)

def test_realized_volatility_uses_absolute_movement():
    window = MarketActivityWindow()

    for minute, ret in enumerate((0.01, -0.01, 0.01, -0.01, 0.01), 1):
        result = window.update((activity(minute * 60, price_return=ret),))[0]

    assert result.realized_volatility_5m == pytest.approx(0.01 * 5 ** 0.5)

def test_out_of_order_activity_rejected():
    window = MarketActivityWindow()
    window.update((activity(120),))

    with pytest.raises(ValueError, match="non-increasing"):
        window.update((activity(60),))

def test_long_gap_resets_warmup():
    window = MarketActivityWindow()
    result = None

    for minute in range(1, 36):
        result = window.update((activity(minute * 60),))[0]

    assert result.warm

    result = window.update((activity(60 * 60),))[0]

    assert not result.warm
    assert result.volume_acceleration_5m is None