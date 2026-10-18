import pytest

from hlbot.backtest.accounting import (
    close_position,
    fee_amount,
    open_position,
    position_notional,
    scale_position,
    total_pnl,
    unrealized_pnl,
)
from hlbot.backtest.execution import SimulatedFill
from hlbot.models.trade import TradeSide
from hlbot.strategy.signal import SignalDirection


def make_fill(side: TradeSide, price: float, quantity: float) -> SimulatedFill:
    notional = price * quantity

    return SimulatedFill(
        side=side,
        timestamp=1000,
        requested_notional=notional,
        filled_notional=notional,
        requested_quantity=None,
        filled_quantity=quantity,
        average_price=price,
        reference_mid_price=price,
        slippage_bps=0,
        levels_consumed=1,
        fully_filled=True
    )

def test_fee_amount():
    assert fee_amount(10000, 1) == pytest.approx(1)
    assert fee_amount(10000, 5) == pytest.approx(5)

def test_open_long_position():
    position = open_position(SignalDirection.LONG, make_fill(TradeSide.BUY, 100, 10), fee_bps=2)

    assert position.quantity == pytest.approx(10)
    assert position.average_entry_price == pytest.approx(100)
    assert position.fees_paid == pytest.approx(0.2)
    assert position.realized_pnl_gross == 0

def test_scale_position_updates_weighted_average():
    position = open_position(SignalDirection.LONG, make_fill(TradeSide.BUY, 100, 10), fee_bps=0)
    position = scale_position(position, make_fill(TradeSide.BUY, 110, 10), fee_bps=0)

    assert position.quantity == pytest.approx(20)
    assert position.average_entry_price == pytest.approx(105)

def test_partial_long_exit_realizes_pnl():
    position = open_position(SignalDirection.LONG, make_fill(TradeSide.BUY, 100, 10), fee_bps=0)
    position = close_position(position, make_fill(TradeSide.SELL, 110, 4), fee_bps=0)

    assert position.quantity == pytest.approx(6)
    assert position.average_entry_price == pytest.approx(100)
    assert position.realized_pnl_gross == pytest.approx(40)

def test_short_position_realizes_pnl():
    position = open_position(SignalDirection.SHORT, make_fill(TradeSide.SELL, 100, 10), fee_bps=0)
    position = close_position(position, make_fill(TradeSide.BUY, 90, 10), fee_bps=0)

    assert position.is_flat
    assert position.average_entry_price == 0
    assert position.realized_pnl_gross == pytest.approx(100)

def test_fees_reduce_net_pnl():
    position = open_position(SignalDirection.LONG, make_fill(TradeSide.BUY, 100, 10), fee_bps=10)
    position = close_position(position, make_fill(TradeSide.SELL, 110, 10), fee_bps=10)

    assert position.realized_pnl_gross == pytest.approx(100)
    assert position.fees_paid == pytest.approx(2.1)
    assert position.realized_pnl_net == pytest.approx(97.9)

def test_unrealized_and_total_pnl():
    position = open_position(SignalDirection.LONG, make_fill(TradeSide.BUY, 100, 10), fee_bps=10)

    assert unrealized_pnl(position, 105) == pytest.approx(50)
    assert position_notional(position, 105) == pytest.approx(1050)
    assert total_pnl(position, 105) == pytest.approx(49)

def test_wrong_fill_side_is_rejected():
    with pytest.raises(ValueError):
        open_position(SignalDirection.LONG, make_fill(TradeSide.SELL, 100, 10), fee_bps=0)

def test_exit_cannot_exceed_position_quantity():
    position = open_position(SignalDirection.LONG, make_fill(TradeSide.BUY, 100, 10), fee_bps=0)

    with pytest.raises(ValueError):
        close_position(position, make_fill(TradeSide.SELL, 110, 11), fee_bps=0)
        
def test_negative_maker_fee_behaves_as_rebate():
    position = open_position(
        SignalDirection.LONG,
        make_fill(TradeSide.BUY, 100, 10),
        fee_bps=-1
    )

    assert position.fees_paid == pytest.approx(-0.1)
    assert position.realized_pnl_net == pytest.approx(0.1)