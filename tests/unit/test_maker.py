import pytest

from hlbot.backtest.maker import place_maker_order, simulate_maker_fill
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
            OrderBookLevel(99, 5),
            OrderBookLevel(98, 10)
        ),
        asks=(
            OrderBookLevel(101, 6),
            OrderBookLevel(102, 10)
        )
    )

def make_trade(timestamp: float, price: float, quantity: float, side: TradeSide, trade_id: str) -> Trade:
    return Trade(
        trade_id=trade_id,
        exchange="hyperliquid_perpetual",
        trading_pair="PONS-USD",
        exchange_ts=timestamp,
        local_ts=timestamp + 0.1,
        price=price,
        quantity=quantity,
        side=side
    )

def test_buy_maker_uses_best_bid_and_visible_queue():
    order = place_maker_order(make_snapshot(), TradeSide.BUY, quantity=2)

    assert order.limit_price == pytest.approx(99)
    assert order.queue_ahead_quantity == pytest.approx(5)

def test_sell_maker_uses_best_ask_and_visible_queue():
    order = place_maker_order(make_snapshot(), TradeSide.SELL, quantity=2)

    assert order.limit_price == pytest.approx(101)
    assert order.queue_ahead_quantity == pytest.approx(6)

def test_maker_order_cannot_cross_spread():
    snapshot = make_snapshot()

    with pytest.raises(ValueError):
        place_maker_order(snapshot, TradeSide.BUY, quantity=1, limit_price=101)

    with pytest.raises(ValueError):
        place_maker_order(snapshot, TradeSide.SELL, quantity=1, limit_price=99)

def test_buy_maker_waits_for_queue_ahead():
    order = place_maker_order(make_snapshot(), TradeSide.BUY, quantity=2)

    trades = [
        make_trade(1001, 99, 3, TradeSide.SELL, "1"),
        make_trade(1002, 99, 2, TradeSide.SELL, "2"),
        make_trade(1003, 99, 1, TradeSide.SELL, "3")
    ]

    fill = simulate_maker_fill(order, trades)

    assert fill.filled_quantity == pytest.approx(1)
    assert fill.queue_ahead_remaining == pytest.approx(0)
    assert fill.first_fill_ts == pytest.approx(1003)
    assert not fill.fully_filled

def test_buy_maker_can_fully_fill_after_queue():
    order = place_maker_order(make_snapshot(), TradeSide.BUY, quantity=2)

    trades = [
        make_trade(1001, 99, 5, TradeSide.SELL, "1"),
        make_trade(1002, 99, 2, TradeSide.SELL, "2")
    ]

    fill = simulate_maker_fill(order, trades)

    assert fill.filled_quantity == pytest.approx(2)
    assert fill.fill_fraction == pytest.approx(1)
    assert fill.fully_filled
    assert fill.first_fill_ts == pytest.approx(1002)
    assert fill.last_fill_ts == pytest.approx(1002)

def test_wrong_aggressor_side_does_not_fill():
    order = place_maker_order(make_snapshot(), TradeSide.BUY, quantity=2)

    trades = [
        make_trade(1001, 99, 100, TradeSide.BUY, "1")
    ]

    fill = simulate_maker_fill(order, trades)

    assert fill.filled_quantity == 0
    assert fill.queue_ahead_remaining == pytest.approx(5)

def test_sell_maker_fill_is_symmetric():
    order = place_maker_order(make_snapshot(), TradeSide.SELL, quantity=2)

    trades = [
        make_trade(1001, 101, 6, TradeSide.BUY, "1"),
        make_trade(1002, 101, 2, TradeSide.BUY, "2")
    ]

    fill = simulate_maker_fill(order, trades)

    assert fill.filled_quantity == pytest.approx(2)
    assert fill.fully_filled

def test_end_timestamp_stops_fill_processing():
    order = place_maker_order(make_snapshot(), TradeSide.BUY, quantity=2)

    trades = [
        make_trade(1001, 99, 5, TradeSide.SELL, "1"),
        make_trade(1005, 99, 2, TradeSide.SELL, "2")
    ]

    fill = simulate_maker_fill(order, trades, end_ts=1002)

    assert fill.filled_quantity == 0