import pytest

from hlbot.models.order_book import OrderBookLevel, OrderBookSnapshot
from hlbot.models.trade import Trade, TradeSide
from hlbot.strategy.market_state import build_market_state, price_return

def make_snapshot(timestamp: float, middle: float) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        exchange="hyperliquid_perpetual",
        trading_pair="PONS-USD",
        exchange_ts=timestamp,
        local_ts=timestamp + 0.1,
        update_id=int(timestamp * 1000),
        bids=(OrderBookLevel(price=middle - 0.01, quantity=200),),
        asks=(OrderBookLevel(price=middle + 0.01, quantity=100),)
    )

def make_trade(timestamp: float, side: TradeSide, quantity: float, trade_id: str) -> Trade:
    return Trade(
        trade_id=trade_id,
        exchange="hyperliquid_perpetual",
        trading_pair="PONS-USD",
        exchange_ts=timestamp,
        local_ts=timestamp + 0.1,
        price=103,
        quantity=quantity,
        side=side
    )

def make_snapshots() -> list[OrderBookSnapshot]:
    return [
        make_snapshot(970, 100),
        make_snapshot(991, 101),
        make_snapshot(995, 102),
        make_snapshot(1000, 103)
    ]

def test_price_return():
    assert price_return(105, 100) == pytest.approx(0.05)

def test_build_market_state():
    snapshots = make_snapshots()
    trades = [
        make_trade(998, TradeSide.BUY, 10, "buy"),
        make_trade(999, TradeSide.SELL, 5, "sell")
    ]

    state = build_market_state(1000, snapshots, trades)

    assert state is not None
    assert state.timestamp == 1000
    assert state.mid_price == pytest.approx(103)
    assert state.imbalance_1 == pytest.approx(1 / 3)
    assert state.imbalance_5 == pytest.approx(1 / 3)
    assert state.weighted_imbalance_5 == pytest.approx(1 / 3)
    assert state.microprice_deviation_bps > 0
    assert state.trade_flow_5s == pytest.approx(1 / 3)
    assert state.volatility_10s > 0
    assert state.bid_liquidity_10bps == pytest.approx(200)
    assert state.ask_liquidity_10bps == pytest.approx(100)
    assert state.return_5s == pytest.approx(103 / 102 - 1)
    assert state.return_30s == pytest.approx(103 / 100 - 1)

def test_unsorted_market_data_is_supported():
    snapshots = list(reversed(make_snapshots()))

    state = build_market_state(1000, snapshots, [])

    assert state is not None
    assert state.mid_price == pytest.approx(103)
    assert state.return_5s == pytest.approx(103 / 102 - 1)

def test_stale_current_snapshot_returns_none():
    snapshots = [
        make_snapshot(950, 100),
        make_snapshot(970, 101)
    ]

    assert build_market_state(1000, snapshots, []) is None

def test_missing_history_returns_none():
    snapshots = [
        make_snapshot(995, 102),
        make_snapshot(1000, 103)
    ]

    assert build_market_state(1000, snapshots, []) is None

def test_invalid_snapshot_age():
    with pytest.raises(ValueError):
        build_market_state(1000, make_snapshots(), [], max_snapshot_age=0)