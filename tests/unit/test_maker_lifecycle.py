import pytest

from hlbot.backtest.maker import place_maker_order
from hlbot.backtest.maker_lifecycle import (
    MakerOrderStatus,
    replace_maker_order,
    simulate_maker_lifecycle,
)
from hlbot.models.order_book import OrderBookLevel, OrderBookSnapshot
from hlbot.models.trade import Trade, TradeSide


def make_snapshot(timestamp: float = 1000, bid_quantity: float = 5) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        exchange="hyperliquid_perpetual",
        trading_pair="PONS-USD",
        exchange_ts=timestamp,
        local_ts=timestamp + 0.1,
        update_id=int(timestamp),
        bids=(
            OrderBookLevel(99, bid_quantity),
            OrderBookLevel(98, 10)
        ),
        asks=(
            OrderBookLevel(101, 6),
            OrderBookLevel(102, 10)
        )
    )

def make_trade(timestamp: float, quantity: float, trade_id: str) -> Trade:
    return Trade(
        trade_id=trade_id,
        exchange="hyperliquid_perpetual",
        trading_pair="PONS-USD",
        exchange_ts=timestamp,
        local_ts=timestamp + 0.1,
        price=99,
        quantity=quantity,
        side=TradeSide.SELL
    )

def test_maker_order_expires():
    order = place_maker_order(make_snapshot(), TradeSide.BUY, quantity=2)
    result = simulate_maker_lifecycle(
        order,
        trades=[make_trade(1002, 3, "1")],
        max_age_seconds=5
    )

    assert result.status == MakerOrderStatus.EXPIRED
    assert result.end_ts == pytest.approx(1005)
    assert result.fill.filled_quantity == 0
    assert result.remaining_quantity == pytest.approx(2)

def test_partial_fill_before_expiry():
    order = place_maker_order(make_snapshot(), TradeSide.BUY, quantity=2)

    trades = [
        make_trade(1001, 5, "1"),
        make_trade(1002, 1, "2")
    ]

    result = simulate_maker_lifecycle(order, trades, max_age_seconds=5)

    assert result.status == MakerOrderStatus.EXPIRED
    assert result.fill.filled_quantity == pytest.approx(1)
    assert result.remaining_quantity == pytest.approx(1)

def test_full_fill_before_expiry():
    order = place_maker_order(make_snapshot(), TradeSide.BUY, quantity=2)

    trades = [
        make_trade(1001, 5, "1"),
        make_trade(1002, 2, "2")
    ]

    result = simulate_maker_lifecycle(order, trades, max_age_seconds=10)

    assert result.status == MakerOrderStatus.FILLED
    assert result.end_ts == pytest.approx(1002)
    assert result.remaining_quantity == pytest.approx(0)

def test_cancel_before_expiry():
    order = place_maker_order(make_snapshot(), TradeSide.BUY, quantity=2)

    trades = [
        make_trade(1002, 5, "1"),
        make_trade(1006, 2, "2")
    ]

    result = simulate_maker_lifecycle(
        order,
        trades,
        max_age_seconds=10,
        cancel_ts=1004
    )

    assert result.status == MakerOrderStatus.CANCELLED
    assert result.end_ts == pytest.approx(1004)
    assert result.fill.filled_quantity == 0

def test_replacement_loses_queue_priority():
    order = place_maker_order(make_snapshot(), TradeSide.BUY, quantity=2)

    result = simulate_maker_lifecycle(
        order,
        trades=[make_trade(1001, 5, "1")],
        max_age_seconds=5
    )

    replacement_snapshot = make_snapshot(timestamp=1005, bid_quantity=8)
    replacement = replace_maker_order(result, replacement_snapshot)

    assert replacement.quantity == pytest.approx(2)
    assert replacement.placed_ts == pytest.approx(1005)
    assert replacement.limit_price == pytest.approx(99)
    assert replacement.queue_ahead_quantity == pytest.approx(8)

def test_replacement_uses_unfilled_quantity():
    order = place_maker_order(make_snapshot(), TradeSide.BUY, quantity=3)

    trades = [
        make_trade(1001, 5, "1"),
        make_trade(1002, 1, "2")
    ]

    result = simulate_maker_lifecycle(order, trades, max_age_seconds=5)
    replacement = replace_maker_order(result, make_snapshot(timestamp=1005))

    assert result.fill.filled_quantity == pytest.approx(1)
    assert replacement.quantity == pytest.approx(2)

def test_filled_order_cannot_be_replaced():
    order = place_maker_order(make_snapshot(), TradeSide.BUY, quantity=1)

    result = simulate_maker_lifecycle(
        order,
        trades=[
            make_trade(1001, 5, "1"),
            make_trade(1002, 1, "2")
        ],
        max_age_seconds=5
    )

    assert result.status == MakerOrderStatus.FILLED

    with pytest.raises(ValueError):
        replace_maker_order(result, make_snapshot(timestamp=1005))

def test_invalid_cancel_time_is_rejected():
    order = place_maker_order(make_snapshot(), TradeSide.BUY, quantity=1)

    with pytest.raises(ValueError):
        simulate_maker_lifecycle(order, [], cancel_ts=999)
        
def test_pending_maker_advances_incrementally():
    from hlbot.backtest.maker_lifecycle import PendingMakerOrder, advance_pending_maker

    order = place_maker_order(make_snapshot(), TradeSide.BUY, quantity=2)
    pending = PendingMakerOrder.from_order(order)

    pending = advance_pending_maker(
        pending,
        [make_trade(1001, 3, "1")]
    )

    assert pending.queue_ahead_remaining == pytest.approx(2)
    assert pending.filled_quantity == 0

    pending = advance_pending_maker(
        pending,
        [make_trade(1002, 3, "2")]
    )

    assert pending.queue_ahead_remaining == 0
    assert pending.filled_quantity == pytest.approx(1)
    assert pending.remaining_quantity == pytest.approx(1)
    assert pending.first_fill_ts == pytest.approx(1002)

def test_pending_maker_can_complete_on_later_step():
    from hlbot.backtest.maker_lifecycle import PendingMakerOrder, advance_pending_maker

    order = place_maker_order(make_snapshot(), TradeSide.BUY, quantity=2)
    pending = PendingMakerOrder.from_order(order)

    pending = advance_pending_maker(
        pending,
        [make_trade(1001, 5, "1")]
    )

    assert not pending.fully_filled

    pending = advance_pending_maker(
        pending,
        [make_trade(1002, 2, "2")]
    )

    assert pending.fully_filled
    assert pending.filled_quantity == pytest.approx(2)
    assert pending.last_fill_ts == pytest.approx(1002)

def test_pending_fill_can_be_exported():
    from hlbot.backtest.maker_lifecycle import (
        PendingMakerOrder,
        advance_pending_maker,
        pending_maker_fill,
    )

    order = place_maker_order(make_snapshot(), TradeSide.BUY, quantity=2)
    pending = PendingMakerOrder.from_order(order)
    pending = advance_pending_maker(
        pending,
        [
            make_trade(1001, 5, "1"),
            make_trade(1002, 1, "2")
        ]
    )

    fill = pending_maker_fill(pending)

    assert fill.requested_quantity == pytest.approx(2)
    assert fill.filled_quantity == pytest.approx(1)
    assert fill.fill_fraction == pytest.approx(0.5)