import argparse
import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from hlbot.data.l2_coverage import check_l2_coverage

def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(path)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--selection",
        default="data/derived/market_selection/collection_universe.json"
    )
    parser.add_argument(
        "--data-dir",
        default="data/raw/hyperliquid_ws_fast"
    )
    parser.add_argument(
        "--output",
        default="data/derived/market_selection/l2_readiness.json"
    )
    parser.add_argument("--window-minutes", type=float, default=60)
    parser.add_argument("--max-gap-seconds", type=float, default=10)
    parser.add_argument("--max-age-seconds", type=float, default=30)
    parser.add_argument("--trading-rank", type=int, default=10)
    args = parser.parse_args()

    selection = json.loads(Path(args.selection).read_text())
    now = time.time()
    rows = []

    for market in selection["markets"]:
        coverage = check_l2_coverage(
            args.data_dir,
            market["coin"],
            now,
            args.window_minutes * 60,
            args.max_gap_seconds,
            args.max_age_seconds
        )

        rows.append({
            "rank": market["rank"],
            **asdict(coverage)
        })

    trading_ready = [
        row for row in rows
        if row["rank"] <= args.trading_rank and row["ready"]
    ]

    write(Path(args.output), {
        "selection_epoch_ts": selection["epoch_ts"],
        "checked_ts": now,
        "checked_utc": datetime.fromtimestamp(now, timezone.utc).isoformat(),
        "window_minutes": args.window_minutes,
        "max_gap_seconds": args.max_gap_seconds,
        "max_age_seconds": args.max_age_seconds,
        "trading_rank": args.trading_rank,
        "ready_coins": [row["coin"] for row in trading_ready],
        "markets": rows
    })

    print(
        f"L2 readiness: {len(trading_ready)}/{args.trading_rank} "
        f"top-ranked markets ready"
    )

    for row in rows:
        marker = "*" if row["rank"] <= args.trading_rank else " "
        gap = row["largest_gap_seconds"]

        print(
            f"{marker}{row['rank']:2}. {row['coin']:<12} "
            f"{row['reason']:<20} "
            f"snapshots={row['snapshots']:<6} "
            f"age={row['latest_age_seconds'] or 0:.1f}s "
            f"gap={gap or 0:.1f}s"
        )

if __name__ == "__main__":
    main()