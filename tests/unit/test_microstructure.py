import pytest

from hlbot.features.liquidity import book_depth_notional, liquidity_notional_within_bps, liquidity_within_bps
from hlbot.features.microprice import microprice, microprice_delta_bps
from hlbot.features.order_book_imbalance import order_book_imbalance, weighted_order_book_imbalance
from hlbot.features.spread import mid_price, spread_bps
from hlbot.models.order_book import OrderBookLevel, OrderBookSnapshot

@pytest.fixture
def snapshot():
    return OrderBookSnapshot(
        exchange="hyperliquid",
        trading_pair="TEST-USD",
        exchange_ts=100,
        local_ts=100.1,
        update_id=1,
        bids=(OrderBookLevel(99, 4), OrderBookLevel(98, 2)),
        asks=(OrderBookLevel(101, 2), OrderBookLevel(102, 2))
    )

def test_mid_price(snapshot):
    assert mid_price(snapshot) == 100

def test_spread_bps(snapshot):
    assert spread_bps(snapshot) == pytest.approx(200)

def test_top_level_imbalance(snapshot):
    assert order_book_imbalance(snapshot) == pytest.approx(1 / 3)

def test_multi_level_imbalance(snapshot):
    assert order_book_imbalance(snapshot, 2) == pytest.approx(0.2)

def test_weighted_imbalance(snapshot):
    assert weighted_order_book_imbalance(snapshot, 2) == pytest.approx(0.25)

def test_microprice(snapshot):
    assert microprice(snapshot) == pytest.approx((101 * 4 + 99 * 2) / 6)

def test_microprice_delta(snapshot):
    assert microprice_delta_bps(snapshot) > 0

def test_base_liquidity_within_bps(snapshot):
    bid, ask = liquidity_within_bps(snapshot, 150)
    assert bid == pytest.approx(4)
    assert ask == pytest.approx(2)

def test_notional_liquidity_within_bps(snapshot):
    bid, ask = liquidity_notional_within_bps(snapshot, 150)
    assert bid == pytest.approx(396)
    assert ask == pytest.approx(202)

def test_book_depth_notional(snapshot):
    bid, ask = book_depth_notional(snapshot, 2)
    assert bid == pytest.approx(592)
    assert ask == pytest.approx(406)