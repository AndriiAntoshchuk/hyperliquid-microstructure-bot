from hlbot.models.order_book import OrderBookLevel, OrderBookSnapshot
from hlbot.models.trade import Trade, TradeSide
from hlbot.research.event_study import capture_market_point, latest_snapshot_before, sample_inactive_times

def make_snapshot(timestamp: float) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        exchange="hyperliquid_perpetual",
        trading_pair="PONS-USD",
        exchange_ts=timestamp,
        local_ts=timestamp + 0.1,
        update_id=int(timestamp * 1000),
        bids=(
            OrderBookLevel(100, 10),
            OrderBookLevel(99.9, 20),
            OrderBookLevel(99.8, 30),
            OrderBookLevel(99.7, 40),
            OrderBookLevel(99.6, 50)
        ),
        asks=(
            OrderBookLevel(100.1, 5),
            OrderBookLevel(100.2, 15),
            OrderBookLevel(100.3, 25),
            OrderBookLevel(100.4, 35),
            OrderBookLevel(100.5, 45)
        )
    )

def make_trade(timestamp: float, side: TradeSide, quantity: float) -> Trade:
    return Trade(
        trade_id=f"{timestamp}:{side.value}:{quantity}",
        exchange="hyperliquid_perpetual",
        trading_pair="PONS-USD",
        exchange_ts=timestamp,
        local_ts=timestamp + 0.1,
        price=100,
        quantity=quantity,
        side=side
    )

def test_latest_snapshot_before():
    snapshots = [make_snapshot(10), make_snapshot(20), make_snapshot(30)]

    assert latest_snapshot_before(snapshots, 25).exchange_ts == 20
    assert latest_snapshot_before(snapshots, 5) is None

def test_capture_market_point():
    snapshots = [make_snapshot(timestamp) for timestamp in range(90, 101)]
    trades = [
        make_trade(97, TradeSide.BUY, 10),
        make_trade(98, TradeSide.SELL, 5),
        make_trade(100, TradeSide.BUY, 5)
    ]

    point = capture_market_point(100, 0, snapshots, trades)

    assert point is not None
    assert point.event_ts == 100
    assert point.market_ts == 100
    assert point.trade_flow_5s == 0.5
    assert point.spread_bps > 0
    assert -1 <= point.imbalance_1 <= 1
    assert -1 <= point.weighted_imbalance_5 <= 1

def test_stale_snapshot_is_rejected():
    snapshots = [make_snapshot(80)]

    assert capture_market_point(100, 0, snapshots, []) is None

def test_sample_inactive_times():
    snapshots = [make_snapshot(timestamp) for timestamp in range(100, 201)]

    class Episode:
        start_ts = 150

    times = sample_inactive_times([Episode()], snapshots, count=10, exclusion_seconds=10)

    assert len(times) == 10
    assert all(abs(timestamp - 150) > 10 for timestamp in times)