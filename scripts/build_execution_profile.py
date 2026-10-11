import argparse
import json
import time
from pathlib import Path

from hlbot.features.execution_profile import build_execution_profile

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
        "--readiness",
        default="data/derived/market_selection/l2_readiness.json"
    )
    parser.add_argument(
        "--data-dir",
        default="data/raw/hyperliquid_ws_fast"
    )
    parser.add_argument(
        "--output",
        default="data/derived/market_selection/execution_profile.json"
    )
    parser.add_argument(
        "--notionals",
        type=float,
        nargs="+",
        default=[100, 250, 500, 750, 1000, 1500, 2000]
    )
    parser.add_argument("--window-minutes", type=float, default=60)
    parser.add_argument("--minimum-full-rate", type=float, default=0.95)
    args = parser.parse_args()

    selection = json.loads(Path(args.selection).read_text())
    readiness = json.loads(Path(args.readiness).read_text())

    if readiness["selection_epoch_ts"] != selection["epoch_ts"]:
        raise SystemExit("L2 readiness belongs to a different selection epoch")

    ready = {
        row["coin"]: row["ready"]
        for row in readiness["markets"]
    }

    now = time.time()

    markets = build_execution_profile(
        selection["markets"],
        ready,
        args.data_dir,
        now,
        args.notionals,
        args.window_minutes * 60,
        args.minimum_full_rate
    )

    write(Path(args.output), {
        "checked_ts": now,
        "selection_epoch_ts": selection["epoch_ts"],
        "window_minutes": args.window_minutes,
        "minimum_full_rate": args.minimum_full_rate,
        "notionals": args.notionals,
        "markets": markets
    })

    supported = sum(
        row["execution_supported"] and row["l2_ready"]
        for row in markets
    )

    print(
        f"Execution profile: {supported} markets analyzed "
        f"| window={args.window_minutes:.0f}m"
    )

    for row in markets:
        if not row["execution_supported"]:
            status = "unsupported"
        elif not row["l2_ready"]:
            status = "L2 not ready"
        else:
            value = row["max_notional"]
            status = "capacity=none" if value is None else f"capacity=${value:.0f}"

        print(f"{row['rank']:2}. {row['coin']:<14} {status}")

if __name__ == "__main__":
    main()