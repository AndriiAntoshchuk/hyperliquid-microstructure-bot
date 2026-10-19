from __future__ import annotations

import argparse
import os
import time
from pathlib import Path


def has_recent_snapshot(data_dir: Path, max_age_seconds: float, now: float | None = None) -> bool:
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")
    current = time.time() if now is None else now
    for path in data_dir.glob("hyperliquid_ws_*_l2Book_*.jsonl"):
        try:
            stat = path.stat()
        except OSError:
            continue
        if stat.st_size > 0 and 0 <= current - stat.st_mtime <= max_age_seconds:
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--max-age-seconds", type=float, default=float(os.environ.get("HEALTH_MAX_AGE_SECONDS", "300")))
    args = parser.parse_args()
    healthy = has_recent_snapshot(args.data_dir, args.max_age_seconds)
    print("healthy" if healthy else "unhealthy: no fresh L2 snapshot")
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
