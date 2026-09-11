import pytest

from hlbot.data.validators import (
    detect_time_gaps,
    find_duplicate_trade_ids,
    validate_order_book_sequence,
    validate_unique_trade_ids
)
from hlbot.models.order_book import OrderBookLevel, OrderBookSnapshot
from hlbot.models.trade import Trade, TradeSide

def make_trade(trade_id: str) -> Trade:
    return Trade(
        trade_id=trade_id,
        exchange="hyperliquid_perpetual",
        trading_pair="PONS-USD",
        exchange_ts=1000,
        local_ts=1000.1,
        price=0.8,
        quantity=100,
        side=TradeSide.BUY
    )


def make_snapshot(update_id: int) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        exchange="hyperliquid_perpetual",
        trading_pair="PONS-USD",
        exchange_ts=float(update_id),
        local_ts=float(update_id) + 0.1,
        update_id=update_id,
        bids=(OrderBookLevel(0.80, 100),),
        asks=(OrderBookLevel(0.81, 100),)
    )


def test_find_duplicate_trade_ids():
    trades = [make_trade("1"), make_trade("2"), make_trade("1")]

    assert find_duplicate_trade_ids(trades) == {"1"}


def test_validate_unique_trade_ids_raises():
    trades = [make_trade("1"), make_trade("1")]

    with pytest.raises(ValueError):
        validate_unique_trade_ids(trades)


def test_order_book_update_ids_must_increase():
    snapshots = [make_snapshot(100), make_snapshot(101), make_snapshot(100)]

    with pytest.raises(ValueError):
        validate_order_book_sequence(snapshots)


def test_detect_time_gaps():
    timestamps = [1.0, 2.0, 3.0, 10.0]
    gaps = detect_time_gaps(timestamps, max_gap_seconds=2.0)

    assert gaps == [(3.0, 10.0, 7.0)]