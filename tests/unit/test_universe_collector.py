import json

import pytest
from hlbot.data.universe_collector import UniverseCollector, fetch_universe_snapshot, parse_asset_contexts

def meta(name="PONS", delisted=False):
    return {
        "universe": [{
            "name": name,
            "szDecimals": 3,
            "maxLeverage": 5,
            "isDelisted": delisted
        }]
    }

def ctx(mid="10"):
    return [{
        "funding": "0.0001",
        "openInterest": "100",
        "prevDayPx": "9",
        "dayNtlVlm": "50000",
        "premium": "0.001",
        "oraclePx": "10.1",
        "markPx": "10.05",
        "midPx": mid,
        "dayBaseVlm": "5000"
    }]

def test_parse_market_context():
    row = parse_asset_contexts(100, "", meta(), ctx())[0]

    assert row.dex == "main"
    assert row.coin == "PONS"
    assert row.day_notional_volume == 50000
    assert row.open_interest == 100
    assert row.mid_price == 10
    assert row.active

def test_delisted_market_is_inactive():
    row = parse_asset_contexts(100, "xyz", meta("xyz:TEST", True), ctx())[0]

    assert row.is_delisted
    assert not row.active

def test_missing_mid_is_supported():
    row = parse_asset_contexts(100, "", meta(), ctx(None))[0]

    assert row.mid_price is None
    assert not row.active

def test_length_mismatch_rejected():
    with pytest.raises(ValueError, match="length mismatch"):
        parse_asset_contexts(100, "", meta(), [])

def test_fetch_snapshot_maps_multiple_dexes():
    responses = {
        "main": [meta("PONS"), ctx()],
        "xyz": [meta("xyz:TEST"), ctx("20")]
    }

    def post(payload):
        dex = payload["dex"] or "main"
        return responses[dex]

    rows = fetch_universe_snapshot(post, ("main", "xyz"), 100)

    assert [row.coin for row in rows] == ["PONS", "xyz:TEST"]
    assert all(row.ts == 100 for row in rows)

def test_collector_writes_jsonl(tmp_path):
    def post(payload):
        if payload["type"] == "perpDexs": return [None]
        return [meta(), ctx()]

    collector = UniverseCollector(tmp_path, post=post)
    rows = collector.collect_once()

    files = list(tmp_path.glob("universe_*.jsonl"))
    assert len(rows) == 1
    assert len(files) == 1

    saved = json.loads(files[0].read_text().strip())
    assert saved["coin"] == "PONS"
    assert saved["day_notional_volume"] == 50000
    
def test_open_interest_notional():
    row = parse_asset_contexts(100, "", meta(), ctx())[0]
    assert row.open_interest_notional == pytest.approx(1005)