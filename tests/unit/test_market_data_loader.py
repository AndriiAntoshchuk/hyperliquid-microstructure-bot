import json

from hlbot.data.market_data_loader import load_order_books, load_trades
from hlbot.models.trade import TradeSide

def test_load_trades(tmp_path):
    path = tmp_path / "trades.jsonl"

    row = {
        "collector_version": "0.2.0",
        "exchange": "hyperliquid_perpetual",
        "trading_pair": "PONS-USD",
        "local_ts": 1000.2,
        "exchange_ts": 1000.0,
        "price": 0.8,
        "q_base": 100,
        "side": "buy",
        "trade_id": "1000000:PONS:123"
    }

    path.write_text(json.dumps(row) + "\n")

    trades = load_trades(path)

    assert len(trades) == 1
    assert trades[0].price == 0.8
    assert trades[0].quantity == 100
    assert trades[0].side == TradeSide.BUY

def test_load_order_books(tmp_path):
    path = tmp_path / "books.jsonl"

    row = {
        "collector_version": "0.2.0",
        "exchange": "hyperliquid_perpetual",
        "trading_pair": "PONS-USD",
        "local_ts": 1000.2,
        "exchange_ts": 1000.0,
        "update_id": 1000000,
        "bids": [[0.80, 100], [0.79, 200]],
        "asks": [[0.81, 100], [0.82, 200]]
    }

    path.write_text(json.dumps(row) + "\n")

    snapshots = load_order_books(path)

    assert len(snapshots) == 1
    assert snapshots[0].best_bid == 0.80
    assert snapshots[0].best_ask == 0.81
    assert len(snapshots[0].bids) == 2

def test_legacy_rows_are_skipped(tmp_path):
    path = tmp_path / "trades.jsonl"
    path.write_text(json.dumps({"ts": 1000, "price": 0.8}) + "\n")

    assert load_trades(path) == []
    
def test_concatenated_json_objects(tmp_path):
    path = tmp_path / "trades.txt"

    row_1 = {
        "exchange": "hyperliquid_perpetual",
        "trading_pair": "PONS-USD",
        "local_ts": 1000.1,
        "exchange_ts": 1000,
        "price": 0.8,
        "q_base": 10,
        "side": "buy",
        "trade_id": "1"
    }

    row_2 = {
        "exchange": "hyperliquid_perpetual",
        "trading_pair": "PONS-USD",
        "local_ts": 1001.1,
        "exchange_ts": 1001,
        "price": 0.81,
        "q_base": 20,
        "side": "sell",
        "trade_id": "2"
    }

    path.write_text(json.dumps(row_1) + json.dumps(row_2))

    trades = load_trades(path)

    assert len(trades) == 2
    assert trades[0].trade_id == "1"
    assert trades[1].trade_id == "2"