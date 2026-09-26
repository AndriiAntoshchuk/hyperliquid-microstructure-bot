import json

from hlbot.data.l2_coverage import check_l2_coverage

def write_books(tmp_path, coin, timestamps):
    path = tmp_path / f"hyperliquid_ws_{coin}_l2Book_2026-09-23.jsonl"

    with path.open("w") as file:
        for ts in timestamps:
            file.write(json.dumps({
                "coin": coin,
                "channel": "l2Book",
                "local_receive_ts": ts
            }) + "\n")

def test_ready_with_full_continuous_window(tmp_path):
    now = 10_000
    write_books(tmp_path, "PONS", range(6400, 10001, 10))

    result = check_l2_coverage(
        tmp_path,
        "PONS",
        now,
        max_gap_seconds=10
    )

    assert result.ready
    assert result.reason == "ready"
    assert result.largest_gap_seconds == 10

def test_insufficient_history(tmp_path):
    now = 10_000
    write_books(tmp_path, "PONS", range(8200, 10001, 10))

    result = check_l2_coverage(tmp_path, "PONS", now)

    assert not result.ready
    assert result.reason == "insufficient_history"

def test_stale_data(tmp_path):
    now = 10_000
    write_books(tmp_path, "PONS", range(6300, 9901, 10))

    result = check_l2_coverage(tmp_path, "PONS", now)

    assert not result.ready
    assert result.reason == "stale"

def test_gap_rejected(tmp_path):
    now = 10_000
    timestamps = list(range(6400, 8001, 10))
    timestamps += list(range(8100, 10001, 10))
    write_books(tmp_path, "PONS", timestamps)

    result = check_l2_coverage(
        tmp_path,
        "PONS",
        now,
        max_gap_seconds=10
    )

    assert not result.ready
    assert result.reason == "gap"
    assert result.largest_gap_seconds == 100

def test_missing_data(tmp_path):
    result = check_l2_coverage(tmp_path, "PONS", 10_000)

    assert not result.ready
    assert result.reason == "no_data"