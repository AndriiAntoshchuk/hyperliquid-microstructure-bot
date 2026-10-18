import pytest

from hlbot.backtest.execution import (
    entry_side,
    execution_slippage_bps,
    exit_side,
    simulate_exit_order,
    simulate_market_order,
    simulate_quantity_order,
)
from hlbot.models.order_book import OrderBookLevel, OrderBookSnapshot
from hlbot.models.trade import TradeSide
from hlbot.strategy.order_intent import OrderIntent, OrderIntentType
from hlbot.strategy.signal import SignalDirection


def make_snapshot() -> OrderBookSnapshot:
    return OrderBookSnapshot(
        exchange="hyperliquid_perpetual",
        trading_pair="PONS-USD",
        exchange_ts=1000,
        local_ts=1000.1,
        update_id=1,
        bids=(
            OrderBookLevel(price=99, quantity=5),
            OrderBookLevel(price=98, quantity=10),
            OrderBookLevel(price=97, quantity=20)
        ),
        asks=(
            OrderBookLevel(price=101, quantity=5),
            OrderBookLevel(price=102, quantity=10),
            OrderBookLevel(price=103, quantity=20)
        )
    )

def make_intent(direction: SignalDirection, notional: float) -> OrderIntent:
    return OrderIntent(
        direction=direction,
        notional=notional,
        intent_type=OrderIntentType.INITIAL_ENTRY,
        scale_index=0,
        signal_strength=0.8,
        reason="test"
    )

def test_entry_and_exit_sides():
    assert entry_side(SignalDirection.LONG) == TradeSide.BUY
    assert entry_side(SignalDirection.SHORT) == TradeSide.SELL
    assert exit_side(SignalDirection.LONG) == TradeSide.SELL
    assert exit_side(SignalDirection.SHORT) == TradeSide.BUY

def test_long_entry_consumes_asks():
    fill = simulate_market_order(
        make_snapshot(),
        make_intent(SignalDirection.LONG, 101)
    )

    assert fill.side == TradeSide.BUY
    assert fill.fully_filled
    assert fill.filled_quantity == pytest.approx(1)
    assert fill.average_price == pytest.approx(101)
    assert fill.levels_consumed == 1
    assert fill.slippage_bps == pytest.approx(100)

def test_short_entry_consumes_bids():
    fill = simulate_market_order(
        make_snapshot(),
        make_intent(SignalDirection.SHORT, 99)
    )

    assert fill.side == TradeSide.SELL
    assert fill.fully_filled
    assert fill.filled_quantity == pytest.approx(1)
    assert fill.average_price == pytest.approx(99)
    assert fill.levels_consumed == 1
    assert fill.slippage_bps == pytest.approx(100)

def test_long_entry_walks_multiple_levels():
    fill = simulate_market_order(
        make_snapshot(),
        make_intent(SignalDirection.LONG, 1015)
    )

    expected_quantity = 5 + 510 / 102
    expected_average = 1015 / expected_quantity

    assert fill.fully_filled
    assert fill.filled_notional == pytest.approx(1015)
    assert fill.filled_quantity == pytest.approx(expected_quantity)
    assert fill.average_price == pytest.approx(expected_average)
    assert fill.levels_consumed == 2

def test_notional_order_can_partially_fill():
    snapshot = make_snapshot()
    total_ask_notional = sum(level.price * level.quantity for level in snapshot.asks)

    fill = simulate_market_order(
        snapshot,
        make_intent(SignalDirection.LONG, 10000)
    )

    assert not fill.fully_filled
    assert fill.filled_notional == pytest.approx(total_ask_notional)
    assert fill.unfilled_notional == pytest.approx(10000 - total_ask_notional)
    assert fill.fill_fraction < 1

def test_quantity_order_walks_book():
    fill = simulate_quantity_order(
        make_snapshot(),
        TradeSide.SELL,
        requested_quantity=8
    )

    assert fill.fully_filled
    assert fill.filled_quantity == pytest.approx(8)
    assert fill.filled_notional == pytest.approx(5 * 99 + 3 * 98)
    assert fill.average_price == pytest.approx((5 * 99 + 3 * 98) / 8)
    assert fill.levels_consumed == 2

def test_long_exit_sells_to_bids():
    fill = simulate_exit_order(
        make_snapshot(),
        SignalDirection.LONG,
        quantity=2
    )

    assert fill.side == TradeSide.SELL
    assert fill.fully_filled
    assert fill.filled_quantity == pytest.approx(2)
    assert fill.average_price == pytest.approx(99)

def test_short_exit_buys_from_asks():
    fill = simulate_exit_order(
        make_snapshot(),
        SignalDirection.SHORT,
        quantity=2
    )

    assert fill.side == TradeSide.BUY
    assert fill.fully_filled
    assert fill.filled_quantity == pytest.approx(2)
    assert fill.average_price == pytest.approx(101)

def test_quantity_exit_can_be_partial():
    fill = simulate_exit_order(
        make_snapshot(),
        SignalDirection.LONG,
        quantity=50
    )

    assert not fill.fully_filled
    assert fill.filled_quantity == pytest.approx(35)
    assert fill.unfilled_quantity == pytest.approx(15)

def test_slippage_is_adverse_for_both_sides():
    assert execution_slippage_bps(
        TradeSide.BUY,
        average_price=101,
        mid_price=100
    ) == pytest.approx(100)

    assert execution_slippage_bps(
        TradeSide.SELL,
        average_price=99,
        mid_price=100
    ) == pytest.approx(100)

def test_none_direction_has_no_execution_side():
    with pytest.raises(ValueError):
        entry_side(SignalDirection.NONE)

    with pytest.raises(ValueError):
        exit_side(SignalDirection.NONE)