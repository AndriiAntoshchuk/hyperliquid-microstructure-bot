import pytest

from hlbot.selection.engine import MarketSelectionSnapshot
from hlbot.selection.market_selector import MarketCandidate
from hlbot.selection.stable_selector import (
    AggregatedMarket,
    StableSelectionConfig,
    aggregate_market_selection,
    build_stable_selection_plan
)

def candidate(coin, score):
    return MarketCandidate(
        ts=100,
        dex="main",
        coin=coin,
        score=score,
        volume_rank=score,
        volume_acceleration_rank=score,
        oi_activity_rank=score,
        price_activity_rank=score,
        available_features=4,
        warm=True
    )

def snapshot(ts, rows):
    return MarketSelectionSnapshot(
        ts=ts,
        markets=(),
        candidates=tuple(candidate(coin, score) for coin, score in rows)
    )

def market(coin, rank, score=0.8, persistence=1):
    return AggregatedMarket(
        "main", coin, rank, score, score, float(rank),
        persistence, 10, 10
    )

def config(**kwargs):
    return StableSelectionConfig(
        entry_rank=2,
        retention_rank=3,
        trading_rank=1,
        **kwargs
    )

def test_persistence_beats_one_snapshot_spike():
    snapshots = tuple(
        snapshot(i * 60, (
            ("A", 0.8),
            *((("B", 1.0),) if i == 6 else ())
        ))
        for i in range(1, 7)
    )

    result = aggregate_market_selection(snapshots)

    assert [row.coin for row in result] == ["A", "B"]
    assert result[0].persistence == pytest.approx(1)
    assert result[1].persistence == pytest.approx(1 / 6)

def test_new_markets_enter_only_inside_entry_rank():
    plan = build_stable_selection_plan(
        (market("A", 1), market("B", 2), market("C", 3)),
        10_000,
        config=config()
    )

    assert [row.coin for row in plan.collection] == ["A", "B"]

def test_existing_market_retained_inside_retention_rank():
    plan = build_stable_selection_plan(
        (market("A", 1), market("B", 2), market("C", 3)),
        10_000,
        {("main", "C"): 1000},
        config()
    )

    assert [row.coin for row in plan.collection] == ["A", "B", "C"]

def test_existing_market_removed_below_retention_rank():
    plan = build_stable_selection_plan(
        (market("A", 1), market("B", 2), market("C", 4)),
        10_000,
        {("main", "C"): 1000},
        config()
    )

    assert [row.coin for row in plan.collection] == ["A", "B"]

def test_new_market_requires_warmup():
    plan = build_stable_selection_plan(
        (market("A", 1),),
        10_000,
        config=config(min_collection_age_seconds=3600)
    )

    row = plan.collection[0]

    assert not row.selection_ready
    assert row.warmup_eligible_at == 13_600
    assert plan.trading_candidates == ()

def test_warmed_top_market_becomes_candidate():
    plan = build_stable_selection_plan(
        (market("A", 1),),
        10_000,
        {("main", "A"): 5000},
        config(min_collection_age_seconds=3600)
    )

    assert [row.coin for row in plan.trading_candidates] == ["A"]

def test_only_trading_rank_becomes_candidate():
    plan = build_stable_selection_plan(
        (market("A", 1), market("B", 2)),
        10_000,
        config=config(min_collection_age_seconds=0)
    )

    assert [row.coin for row in plan.trading_candidates] == ["A"]

def test_collection_since_is_preserved():
    plan = build_stable_selection_plan(
        (market("A", 1),),
        10_000,
        {("main", "A"): 1234},
        config()
    )

    assert plan.collection[0].collection_since == 1234

def test_invalid_retention_rank_rejected():
    with pytest.raises(ValueError):
        StableSelectionConfig(entry_rank=20, retention_rank=10)

def test_empty_snapshots_return_empty():
    assert aggregate_market_selection(()) == ()