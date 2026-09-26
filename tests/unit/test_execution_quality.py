import json

import pytest

from hlbot.features.execution_quality import (
    analyze_execution_quality,
    percentile,
    walk_book,
    walk_book_many
)

def write_books(tmp_path, coin, rows):
    path = tmp_path / f"hyperliquid_ws_{coin}_l2Book_2026-09-23.jsonl"

    with path.open("w") as file:
        for ts, bids, asks in rows:
            file.write(json.dumps({
                "local_receive_ts": ts,
                "data": {
                    "coin": coin,
                    "levels": [
                        [{"px": str(px), "sz": str(sz)} for px, sz in bids],
                        [{"px": str(px), "sz": str(sz)} for px, sz in asks]
                    ]
                }
            }) + "\n")

def test_percentile():
    assert percentile([1, 2, 3, 4, 5], 0.5) == 3

def test_walk_book_single_level():
    assert walk_book(((100, 10),), 500) == pytest.approx(100)

def test_walk_book_insufficient_depth():
    assert walk_book(((100, 1),), 500) is None

def test_execution_quality(tmp_path):
    rows = [
        (
            9990 + i,
            [(99, 20)],
            [(101, 20)]
        )
        for i in range(10)
    ]
    write_books(tmp_path, "PONS", rows)

    result = analyze_execution_quality(
        tmp_path,
        "PONS",
        now=10_000,
        notional=100,
        window_seconds=60
    )

    assert result.snapshots == 10
    assert result.buy_full_rate == 1
    assert result.sell_full_rate == 1
    assert result.buy_slippage_p50_bps == pytest.approx(0)
    assert result.sell_slippage_p50_bps == pytest.approx(0)
    assert result.round_trip_p90_bps == pytest.approx(0)
    assert result.two_sided_depth_p10 == pytest.approx(1980)

def test_partial_depth_reduces_full_rate(tmp_path):
    write_books(tmp_path, "PONS", [
        (9998, [(99, 20)], [(101, 20)]),
        (9999, [(99, 1)], [(101, 1)])
    ])

    result = analyze_execution_quality(
        tmp_path,
        "PONS",
        now=10_000,
        notional=500,
        window_seconds=60
    )

    assert result.buy_full_rate == pytest.approx(0.5)
    assert result.sell_full_rate == pytest.approx(0.5)

def test_walk_book_many_matches_single_walk():
    levels = (
        (100, 2),
        (101, 3),
        (102, 5)
    )
    notionals = (100, 250, 500, 750)

    result = walk_book_many(levels, notionals)

    for notional in notionals:
        assert result[notional] == pytest.approx(
            walk_book(levels, notional)
        )

def test_walk_book_many_marks_insufficient_depth():
    result = walk_book_many(
        ((100, 1),),
        (50, 100, 200)
    )

    assert result[50] == pytest.approx(100)
    assert result[100] == pytest.approx(100)
    assert result[200] is None