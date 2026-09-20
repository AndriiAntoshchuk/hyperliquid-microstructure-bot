import pytest

from hlbot.execution.account_tracker import AccountTracker
from hlbot.execution.fill import ExecutionFill
from hlbot.models.trade import TradeSide

def fill(
    fill_id: str,
    side: TradeSide,
    quantity: float,
    price: float,
    fee: float = 0,
    coin: str = "TEST",
    timestamp: float = 100
) -> ExecutionFill:
    return ExecutionFill(
        fill_id,
        "order-1",
        coin,
        side,
        quantity,
        price,
        fee,
        timestamp
    )

def test_open_long_position():
    tracker = AccountTracker(10000)
    tracker.apply_fill(fill("1", TradeSide.BUY, 2, 100))

    position = tracker.position("TEST")

    assert position.quantity == 2
    assert position.average_entry_price == 100
    assert position.direction == "long"

def test_scale_into_long_updates_average_price():
    tracker = AccountTracker(10000)
    tracker.apply_fill(fill("1", TradeSide.BUY, 2, 100))
    tracker.apply_fill(fill("2", TradeSide.BUY, 2, 110))

    position = tracker.position("TEST")

    assert position.quantity == 4
    assert position.average_entry_price == 105

def test_partial_long_close_realizes_pnl():
    tracker = AccountTracker(10000)
    tracker.apply_fill(fill("1", TradeSide.BUY, 2, 100))
    tracker.apply_fill(fill("2", TradeSide.SELL, 1, 110))

    assert tracker.position("TEST").quantity == 1
    assert tracker.position("TEST").average_entry_price == 100
    assert tracker.gross_realized_pnl == 10

def test_short_position_profit():
    tracker = AccountTracker(10000)
    tracker.apply_fill(fill("1", TradeSide.SELL, 2, 100))
    tracker.apply_fill(fill("2", TradeSide.BUY, 2, 90))

    assert tracker.position("TEST").direction == "flat"
    assert tracker.gross_realized_pnl == 20

def test_position_flip_uses_fill_price_as_new_entry():
    tracker = AccountTracker(10000)
    tracker.apply_fill(fill("1", TradeSide.BUY, 1, 100))
    tracker.apply_fill(fill("2", TradeSide.SELL, 2, 110))

    position = tracker.position("TEST")

    assert position.quantity == -1
    assert position.average_entry_price == 110
    assert tracker.gross_realized_pnl == 10

def test_fees_reduce_realized_pnl():
    tracker = AccountTracker(10000)
    tracker.apply_fill(fill("1", TradeSide.BUY, 1, 100, fee=1))
    tracker.apply_fill(fill("2", TradeSide.SELL, 1, 110, fee=1))

    assert tracker.gross_realized_pnl == 10
    assert tracker.fees == 2
    assert tracker.realized_pnl == 8

def test_mark_updates_unrealized_pnl_and_equity():
    tracker = AccountTracker(10000)
    tracker.apply_fill(fill("1", TradeSide.BUY, 2, 100))
    tracker.update_mark("TEST", 110)

    assert tracker.unrealized_pnl == 20
    assert tracker.equity == 10020
    assert tracker.position_notional("TEST") == 220

def test_short_unrealized_pnl():
    tracker = AccountTracker(10000)
    tracker.apply_fill(fill("1", TradeSide.SELL, 2, 100))
    tracker.update_mark("TEST", 90)

    assert tracker.unrealized_pnl == 20
    assert tracker.equity == 10020

def test_peak_equity_and_drawdown():
    tracker = AccountTracker(10000)
    tracker.apply_fill(fill("1", TradeSide.BUY, 1, 100))

    tracker.update_mark("TEST", 110)
    assert tracker.peak_equity == 10010

    tracker.update_mark("TEST", 90)
    snapshot = tracker.snapshot()

    assert snapshot.equity == 9990
    assert snapshot.peak_equity == 10010
    assert snapshot.drawdown_pct == pytest.approx((20 / 10010) * 100)

def test_duplicate_fill_is_rejected():
    tracker = AccountTracker(10000)
    trade = fill("1", TradeSide.BUY, 1, 100)

    tracker.apply_fill(trade)

    with pytest.raises(ValueError):
        tracker.apply_fill(trade)

def test_daily_realized_pnl_includes_fees():
    tracker = AccountTracker(10000)

    tracker.apply_fill(fill("1", TradeSide.BUY, 1, 100, fee=1, timestamp=1_700_000_000))
    tracker.apply_fill(fill("2", TradeSide.SELL, 1, 110, fee=1, timestamp=1_700_000_100))

    assert tracker.realized_pnl_for_day(1_700_000_200) == 8

def test_positions_returns_known_positions():
    tracker = AccountTracker(10000)
    tracker.apply_fill(fill("1", TradeSide.BUY, 1, 100, coin="PURR"))
    tracker.apply_fill(fill("2", TradeSide.SELL, 2, 50, coin="PONS"))

    positions = tracker.positions()

    assert [position.coin for position in positions] == ["PONS", "PURR"]