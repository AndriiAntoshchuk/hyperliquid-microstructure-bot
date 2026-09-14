import json

from hlbot.data.hyperliquid_ws_loader import load_ws_market_data, load_ws_order_books, load_ws_trades
from hlbot.models.trade import TradeSide

def make_book_record(timestamp_ms: int = 1000000) -> dict:
    return {
        "collector_version": "0.1.0",
        "source": "hyperliquid_websocket",
        "coin": "PONS",
        "channel": "l2Book",
        "local_receive_ns": 1000500000000,
        "local_receive_ts": 1000.5,
        "connection_id": "abc",
        "message_index": 1,
        "data": {
            "coin": "PONS",
            "time": timestamp_ms,
            "levels": [
                [
                    {"px": "0.6058", "sz": "100", "n": 1},
                    {"px": "0.6057", "sz": "200", "n": 1}
                ],
                [
                    {"px": "0.6059", "sz": "150", "n": 1},
                    {"px": "0.6060", "sz": "250", "n": 1}
                ]
            ]
        }
    }

def make_trade_record() -> dict:
    return {
        "collector_version": "0.1.0",
        "source": "hyperliquid_websocket",
        "coin": "PONS",
        "channel": "trades",
        "local_receive_ns": 1000500000000,
        "local_receive_ts": 1000.5,
        "connection_id": "abc",
        "message_index": 2,
        "data": [
            {
                "coin": "PONS",
                "side": "B",
                "px": "0.6058",
                "sz": "10",
                "time": 1000000,
                "hash": "0x1",
                "tid": 123
            },
            {
                "coin": "PONS",
                "side": "A",
                "px": "0.6057",
                "sz": "20",
                "time": 1000100,
                "hash": "0x2",
                "tid": 456
            }
        ]
    }

def test_load_ws_order_books(tmp_path):
    path = tmp_path / "books.jsonl"
    path.write_text(json.dumps(make_book_record()) + "\n")

    snapshots = load_ws_order_books(path)

    assert len(snapshots) == 1
    assert snapshots[0].exchange == "hyperliquid_perpetual"
    assert snapshots[0].trading_pair == "PONS-USD"
    assert snapshots[0].exchange_ts == 1000
    assert snapshots[0].local_ts == 1000.5
    assert snapshots[0].best_bid == 0.6058
    assert snapshots[0].best_ask == 0.6059
    assert len(snapshots[0].bids) == 2
    assert len(snapshots[0].asks) == 2

def test_load_ws_trades(tmp_path):
    path = tmp_path / "trades.jsonl"
    path.write_text(json.dumps(make_trade_record()) + "\n")

    trades = load_ws_trades(path)

    assert len(trades) == 2
    assert trades[0].trade_id == "1000000:PONS:123"
    assert trades[0].side == TradeSide.BUY
    assert trades[0].price == 0.6058
    assert trades[0].quantity == 10
    assert trades[1].side == TradeSide.SELL

def test_duplicate_ws_trades_are_removed(tmp_path):
    path = tmp_path / "trades.jsonl"
    record = make_trade_record()

    path.write_text(
        json.dumps(record) + "\n" +
        json.dumps(record) + "\n"
    )

    trades = load_ws_trades(path)

    assert len(trades) == 2
    assert len({trade.trade_id for trade in trades}) == 2

def test_load_ws_market_data_across_files(tmp_path):
    first_book = tmp_path / "hyperliquid_ws_PONS_l2Book_2026-09-12.jsonl"
    second_book = tmp_path / "hyperliquid_ws_PONS_l2Book_2026-09-13.jsonl"
    first_trades = tmp_path / "hyperliquid_ws_PONS_trades_2026-09-12.jsonl"
    second_trades = tmp_path / "hyperliquid_ws_PONS_trades_2026-09-13.jsonl"

    first_book.write_text(json.dumps(make_book_record(1000000)) + "\n")
    second_book.write_text(json.dumps(make_book_record(2000000)) + "\n")

    trade_record = make_trade_record()
    first_trades.write_text(json.dumps(trade_record) + "\n")
    second_trades.write_text(json.dumps(trade_record) + "\n")

    snapshots, trades = load_ws_market_data(tmp_path, "PONS")

    assert len(snapshots) == 2
    assert snapshots[0].exchange_ts == 1000
    assert snapshots[1].exchange_ts == 2000
    assert len(trades) == 2