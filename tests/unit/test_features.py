import pytest

from hlbot.features.liquidity import liquidity_within_bps
from hlbot.features.microprice import microprice
from hlbot.features.order_book_imbalance import order_book_imbalance, weighted_order_book_imbalance
from hlbot.features.spread import mid_price, spread, spread_bps
from hlbot.features.trade_flow import buy_sell_volume, rolling_trade_flow_imbalance, trade_flow_imbalance, trades_in_window
from hlbot.features.volatility import log_returns, volatility
from hlbot.models.order_book import OrderBookLevel, OrderBookSnapshot
from hlbot.models.trade import Trade, TradeSide

def make_snapshot() -> OrderBookSnapshot:
    return OrderBookSnapshot(
        exchange="hyperliquid_perpetual",
        trading_pair="PONS-USD",
        exchange_ts=1000,
        local_ts=1000.1,
        update_id=1,
        bids=(
            OrderBookLevel(100, 10),
            OrderBookLevel(99, 20),
            OrderBookLevel(98, 30)
        ),
        asks=(
            OrderBookLevel(101, 5),
            OrderBookLevel(102, 15),
            OrderBookLevel(103, 25)
        )
    )

def make_trade(timestamp: float, quantity: float, side: TradeSide) -> Trade:
    return Trade(
        trade_id=f"{timestamp}:{side.value}:{quantity}",
        exchange="hyperliquid_perpetual",
        trading_pair="PONS-USD",
        exchange_ts=timestamp,
        local_ts=timestamp + 0.1,
        price=100,
        quantity=quantity,
        side=side
    )

def test_spread_features():
    snapshot = make_snapshot()

    assert mid_price(snapshot) == 100.5
    assert spread(snapshot) == 1
    assert spread_bps(snapshot) == pytest.approx(99.50248756)

def test_order_book_imbalance():
    snapshot = make_snapshot()

    assert order_book_imbalance(snapshot, 1) == pytest.approx((10 - 5) / 15)
    assert order_book_imbalance(snapshot, 2) == pytest.approx((30 - 20) / 50)

def test_weighted_order_book_imbalance():
    snapshot = make_snapshot()

    result = weighted_order_book_imbalance(snapshot, 2)

    bid_volume = 10 + 20 / 2
    ask_volume = 5 + 15 / 2

    assert result == pytest.approx((bid_volume - ask_volume) / (bid_volume + ask_volume))

def test_microprice():
    snapshot = make_snapshot()

    expected = (101 * 10 + 100 * 5) / 15

    assert microprice(snapshot) == pytest.approx(expected)

def test_trade_flow():
    trades = [
        make_trade(1, 10, TradeSide.BUY),
        make_trade(2, 5, TradeSide.SELL),
        make_trade(3, 5, TradeSide.BUY)
    ]

    buy_volume, sell_volume = buy_sell_volume(trades)

    assert buy_volume == 15
    assert sell_volume == 5
    assert trade_flow_imbalance(trades) == pytest.approx(0.5)

def test_trade_window():
    trades = [
        make_trade(1, 10, TradeSide.BUY),
        make_trade(5, 5, TradeSide.SELL),
        make_trade(10, 20, TradeSide.BUY)
    ]

    result = trades_in_window(trades, end_ts=10, window_seconds=6)

    assert len(result) == 2
    assert result[0].exchange_ts == 5
    assert result[1].exchange_ts == 10
    assert rolling_trade_flow_imbalance(trades, 10, 6) == pytest.approx(0.6)

def test_log_returns_and_volatility():
    prices = [100, 101, 102]

    returns = log_returns(prices)

    assert len(returns) == 2
    assert returns[0] > 0
    assert volatility(prices) >= 0

def test_liquidity_within_bps():
    snapshot = make_snapshot()

    bid_liquidity, ask_liquidity = liquidity_within_bps(snapshot, 150)

    assert bid_liquidity == 30
    assert ask_liquidity == 20

def test_invalid_parameters():
    snapshot = make_snapshot()

    with pytest.raises(ValueError):
        order_book_imbalance(snapshot, 0)

    with pytest.raises(ValueError):
        weighted_order_book_imbalance(snapshot, 0)

    with pytest.raises(ValueError):
        liquidity_within_bps(snapshot, 0)

    with pytest.raises(ValueError):
        trades_in_window([], 10, 0)

    with pytest.raises(ValueError):
        log_returns([100, 0])