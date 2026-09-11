import pytest

from hlbot.models.trade import Trade, TradeSide

def test_trade_creation():
    trade = Trade(
        trade_id="123:PONS:456",
        exchange="hyperliquid_perpetual",
        trading_pair="PONS-USD",
        exchange_ts=1000.0,
        local_ts=1000.2,
        price=0.8,
        quantity=100,
        side=TradeSide.BUY,
    )

    assert trade.price == 0.8
    assert trade.side == TradeSide.BUY


def test_trade_rejects_negative_quantity():
    with pytest.raises(ValueError):
        Trade(
            trade_id="123",
            exchange="hyperliquid_perpetual",
            trading_pair="PONS-USD",
            exchange_ts=1000,
            local_ts=1000,
            price=0.8,
            quantity=-1,
            side=TradeSide.BUY,
        )