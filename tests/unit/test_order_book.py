import pytest

from hlbot.models.order_book import OrderBookLevel, OrderBookSnapshot

def test_order_book_snapshot():
    snapshot = OrderBookSnapshot(
        exchange="hyperliquid_perpetual",
        trading_pair="PONS-USD",
        exchange_ts=1000,
        local_ts=1000.2,
        update_id=123,
        bids=(
            OrderBookLevel(0.80, 100),
            OrderBookLevel(0.79, 200),
        ),
        asks=(
            OrderBookLevel(0.81, 100),
            OrderBookLevel(0.82, 200),
        ),
    )

    assert snapshot.best_bid == 0.80
    assert snapshot.best_ask == 0.81
    assert snapshot.mid_price == pytest.approx(0.805)
    assert snapshot.spread == pytest.approx(0.01)

def test_crossed_order_book_is_rejected():
    with pytest.raises(ValueError):
        OrderBookSnapshot(
            exchange="hyperliquid_perpetual",
            trading_pair="PONS-USD",
            exchange_ts=1000,
            local_ts=1000,
            update_id=123,
            bids=(OrderBookLevel(0.82, 100),),
            asks=(OrderBookLevel(0.81, 100),),
        )