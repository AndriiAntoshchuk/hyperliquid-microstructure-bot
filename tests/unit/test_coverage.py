import pytest

from hlbot.data.coverage import find_coverage_segments, timestamp_has_coverage
from hlbot.models.order_book import OrderBookLevel, OrderBookSnapshot

def make_snapshot(timestamp: float) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        exchange="hyperliquid_perpetual",
        trading_pair="PONS-USD",
        exchange_ts=timestamp,
        local_ts=timestamp + 0.1,
        update_id=int(timestamp * 1000),
        bids=(OrderBookLevel(100, 10),),
        asks=(OrderBookLevel(101, 10),)
    )

def test_find_coverage_segments():
    snapshots = [
        make_snapshot(1),
        make_snapshot(6),
        make_snapshot(11),
        make_snapshot(101),
        make_snapshot(106)
    ]

    segments = find_coverage_segments(snapshots, max_gap_seconds=15)

    assert len(segments) == 2
    assert segments[0].start_ts == 1
    assert segments[0].end_ts == 11
    assert segments[0].snapshots == 3
    assert segments[1].start_ts == 101
    assert segments[1].end_ts == 106

def test_timestamp_has_coverage():
    segments = find_coverage_segments(
        [make_snapshot(timestamp) for timestamp in range(1, 102, 5)],
        max_gap_seconds=15
    )

    assert timestamp_has_coverage(51, segments, margin_seconds=30)
    assert not timestamp_has_coverage(11, segments, margin_seconds=30)
    assert not timestamp_has_coverage(96, segments, margin_seconds=30)

def test_invalid_gap():
    with pytest.raises(ValueError):
        find_coverage_segments([], 0)