import argparse
import json
from collections import Counter
from pathlib import Path

from hlbot.data.universe_collector import UniverseMarket
from hlbot.features.market_activity import MarketActivityTracker
from hlbot.features.market_activity_window import MarketActivityWindow
from hlbot.selection.market_selector import MarketSelector, MarketSelectorConfig

def snapshots(paths):
    current_ts = None
    rows = []

    for path in paths:
        with path.open() as file:
            for line in file:
                row = UniverseMarket(**json.loads(line))

                if current_ts is not None and row.ts != current_ts:
                    yield tuple(rows)
                    rows = []

                current_ts = row.ts
                rows.append(row)

    if rows: yield tuple(rows)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/raw/hyperliquid_universe")
    parser.add_argument("--top-n", type=int, default=10)
    args = parser.parse_args()

    paths = sorted(Path(args.input).glob("universe_*.jsonl"))
    if not paths: raise SystemExit("no universe files found")

    tracker = MarketActivityTracker()
    window = MarketActivityWindow()
    selector = MarketSelector(MarketSelectorConfig(top_n=args.top_n))
    selected = Counter()
    latest = ()
    snapshots_seen = warm_snapshots = 0

    for snapshot in snapshots(paths):
        snapshots_seen += 1
        activities = tracker.update(snapshot)
        if not activities: continue

        rolling = window.update(activities)
        candidates = selector.select(rolling)
        if not candidates or not any(row.warm for row in candidates): continue

        warm_snapshots += 1
        latest = candidates
        selected.update((row.dex, row.coin) for row in candidates)

    print(f"files={len(paths)} snapshots={snapshots_seen} warm_snapshots={warm_snapshots}")

    print("\nLatest top markets:")
    for i, row in enumerate(latest, 1):
        print(
            f"{i:2}. {row.coin:<18} score={row.score:.3f} "
            f"vol={_fmt(row.volume_rank)} "
            f"accel={_fmt(row.volume_acceleration_rank)} "
            f"oi={_fmt(row.oi_activity_rank)} "
            f"price={_fmt(row.price_activity_rank)} "
            f"warm={row.warm}"
        )

    print("\nMost frequently selected:")
    for i, ((dex, coin), count) in enumerate(selected.most_common(20), 1):
        share = count / warm_snapshots if warm_snapshots else 0
        print(f"{i:2}. {coin:<18} dex={dex:<6} selected={count:<5} share={share:.1%}")

def _fmt(value):
    return "-" if value is None else f"{value:.2f}"

if __name__ == "__main__":
    main()