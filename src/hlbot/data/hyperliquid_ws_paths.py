from datetime import UTC, datetime
from pathlib import Path


def utc_date_from_ns(timestamp_ns: int) -> str:
    return datetime.fromtimestamp(timestamp_ns / 1_000_000_000, UTC).strftime("%Y-%m-%d")

def output_path(data_dir: str | Path, coin: str, channel: str, timestamp_ns: int) -> Path:
    return Path(data_dir) / f"hyperliquid_ws_{coin}_{channel}_{utc_date_from_ns(timestamp_ns)}.jsonl"
