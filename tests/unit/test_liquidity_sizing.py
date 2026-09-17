import pytest

from hlbot.models.order_book import OrderBookLevel, OrderBookSnapshot
from hlbot.strategy.liquidity_sizing import liquidity_capped_notional, safe_visible_notional, visible_notional

def make_snapshot():
    return OrderBookSnapshot(
        "hyperliquid_perpetual",
        "TEST-USD",
        1000,
        1000.1,
        1,
        (OrderBookLevel(99, 10), OrderBookLevel(98, 10)),
        (OrderBookLevel(101, 20), OrderBookLevel(102, 20))
    )

def test_visible_notional():
    bid, ask = visible_notional(make_snapshot())
    assert bid == pytest.approx(1970)
    assert ask == pytest.approx(4060)

def test_safe_visible_notional():
    assert safe_visible_notional(make_snapshot()) == pytest.approx(1970)

def test_liquidity_capped_notional():
    snapshot = make_snapshot()
    assert liquidity_capped_notional(snapshot, 1000, .25) == pytest.approx(492.5)
    assert liquidity_capped_notional(snapshot, 100, .25) == pytest.approx(100)

def test_invalid_liquidity_fraction():
    with pytest.raises(ValueError): liquidity_capped_notional(make_snapshot(), 1000, 0)