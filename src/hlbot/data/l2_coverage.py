import json
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class L2Coverage:
    coin: str
    ready: bool
    reason: str
    snapshots: int
    first_ts: float | None
    last_ts: float | None
    span_seconds: float
    latest_age_seconds: float | None
    largest_gap_seconds: float | None

def reverse_lines(path: Path, block_size: int = 65536):
    with path.open("rb") as file:
        file.seek(0, 2)
        position = file.tell()
        buffer = b""

        while position:
            size = min(block_size, position)
            position -= size
            file.seek(position)
            buffer = file.read(size) + buffer
            lines = buffer.split(b"\n")
            buffer = lines[0]

            for line in reversed(lines[1:]):
                if line: yield line.decode()

        if buffer: yield buffer.decode()

def recent_timestamps(data_dir: str | Path, coin: str, cutoff: float):
    timestamps = []
    pattern = f"hyperliquid_ws_{coin}_l2Book_*.jsonl"

    for path in reversed(sorted(Path(data_dir).glob(pattern))):
        for line in reverse_lines(path):
            try:
                ts = float(json.loads(line)["local_receive_ts"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue

            timestamps.append(ts)
            if ts <= cutoff: return tuple(sorted(timestamps))

    return tuple(sorted(timestamps))

def check_l2_coverage(
    data_dir: str | Path,
    coin: str,
    now: float,
    window_seconds: float = 3600,
    max_gap_seconds: float = 10,
    max_age_seconds: float = 30
) -> L2Coverage:
    cutoff = now - window_seconds
    timestamps = recent_timestamps(data_dir, coin, cutoff)

    if not timestamps:
        return L2Coverage(coin, False, "no_data", 0, None, None, 0, None, None)

    first, last = timestamps[0], timestamps[-1]
    gaps = [b - a for a, b in zip(timestamps, timestamps[1:]) if b >= a]
    largest_gap = max(gaps, default=0)
    age = max(0, now - last)
    span = max(0, last - first)

    if first > cutoff:
        reason = "insufficient_history"
    elif age > max_age_seconds:
        reason = "stale"
    elif largest_gap > max_gap_seconds:
        reason = "gap"
    else:
        reason = "ready"

    return L2Coverage(
        coin,
        reason == "ready",
        reason,
        len(timestamps),
        first,
        last,
        span,
        age,
        largest_gap
    )