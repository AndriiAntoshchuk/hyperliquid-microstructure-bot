import pytest

from hlbot.data.universe_collector import UniverseMarket
from hlbot.selection.engine import MarketSelectionEngine
from hlbot.selection.market_selector import MarketSelectorConfig

def market(ts, coin, volume, oi, mark):
    return UniverseMarket(
        ts=ts,
        dex="main",
        coin=coin,
        is_delisted=False,
        sz_decimals=3,
        max_leverage=5,
        day_notional_volume=volume,
        day_base_volume=100,
        open_interest=oi,
        funding=0.0001,
        premium=0.001,
        oracle_price=mark,
        mark_price=mark,
        mid_price=mark,
        prev_day_price=mark
    )

def test_first_snapshot_has_no_candidates():
    engine = MarketSelectionEngine()
    result = engine.update((market(100, "A", 1000, 100, 10),))

    assert result.ts == 100
    assert result.markets == ()
    assert result.candidates == ()

def test_engine_selects_high_activity_market():
    engine = MarketSelectionEngine(MarketSelectorConfig(top_n=1))
    engine.update((
        market(100, "A", 20_000_000, 100, 10),
        market(100, "B", 20_000_000, 100, 10)
    ))

    result = engine.update((
        market(160, "A", 20_000_100, 101, 10.01),
        market(160, "B", 20_000_500, 110, 10.5)
    ))

    assert result.coins == ("B",)
    
def test_long_gap_produces_no_contaminated_activity():
    engine = MarketSelectionEngine()
    engine.update((market(100, "A", 1000, 100, 10),))

    result = engine.update((market(300, "A", 5000, 150, 12),))

    assert result.markets == ()
    assert result.candidates == ()

def test_snapshot_timestamp_mismatch_rejected():
    engine = MarketSelectionEngine()

    with pytest.raises(ValueError, match="timestamps"):
        engine.update((
            market(100, "A", 1000, 100, 10),
            market(101, "B", 1000, 100, 10)
        ))

def test_empty_snapshot_rejected():
    with pytest.raises(ValueError, match="empty"):
        MarketSelectionEngine().update(())