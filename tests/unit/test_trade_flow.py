import pytest

from hlbot.features.trade_flow import rolling_trade_flow_features, rolling_trade_flow_imbalance
from hlbot.models.trade import Trade, TradeSide

def trade(trade_id, ts, quantity, side):
    return Trade(
        trade_id=trade_id,
        exchange="hyperliquid",
        trading_pair="TEST-USD",
        exchange_ts=ts,
        local_ts=ts + 0.01,
        price=100,
        quantity=quantity,
        side=side
    )

def test_rolling_trade_flow_imbalance():
    trades = [
        trade("1", 96, 20, TradeSide.SELL),
        trade("2", 99.5, 30, TradeSide.BUY),
        trade("3", 100, 10, TradeSide.SELL)
    ]
    assert rolling_trade_flow_imbalance(trades, 100, 1) == pytest.approx(0.5)

def test_rolling_trade_flow_features():
    trades = [
        trade("1", 96, 20, TradeSide.SELL),
        trade("2", 99.5, 30, TradeSide.BUY),
        trade("3", 100, 10, TradeSide.SELL)
    ]
    result = rolling_trade_flow_features(trades, 100, windows=(1, 5))
    assert result["buy_volume_1s"] == 30
    assert result["sell_volume_1s"] == 10
    assert result["tfi_1s"] == pytest.approx(0.5)
    assert result["buy_volume_5s"] == 30
    assert result["sell_volume_5s"] == 30
    assert result["tfi_5s"] == pytest.approx(0)