from datetime import datetime, timezone

from hlbot.data.hyperliquid_ws_collector import build_record, output_path, utc_date_from_ns

def test_utc_date_from_ns():
    timestamp = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)
    timestamp_ns = int(timestamp.timestamp() * 1_000_000_000)

    assert utc_date_from_ns(timestamp_ns) == "2026-09-12"

def test_output_path():
    timestamp = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)
    timestamp_ns = int(timestamp.timestamp() * 1_000_000_000)

    path = output_path("data", "PONS", "l2Book", timestamp_ns)

    assert path.name == "hyperliquid_ws_PONS_l2Book_2026-09-12.jsonl"

def test_build_record():
    record = build_record(
        channel="l2Book",
        data={"coin": "PONS", "time": 123, "levels": [[], []]},
        coin="PONS",
        connection_id="abc",
        message_index=7,
        received_ns=1_000_000_000
    )

    assert record["source"] == "hyperliquid_websocket"
    assert record["coin"] == "PONS"
    assert record["channel"] == "l2Book"
    assert record["local_receive_ns"] == 1_000_000_000
    assert record["local_receive_ts"] == 1.0
    assert record["connection_id"] == "abc"
    assert record["message_index"] == 7
    assert record["data"]["coin"] == "PONS"