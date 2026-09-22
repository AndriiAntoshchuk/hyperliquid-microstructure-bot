import argparse
import json
from bisect import bisect_left
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

from hlbot.data.universe_collector import UniverseMarket
from hlbot.features.market_activity import MarketActivityTracker
from hlbot.features.market_activity_window import MarketActivityWindow
from hlbot.selection.market_selector import MarketSelector, MarketSelectorConfig

METRICS = ("price", "volume", "oi")
BUCKETS = (
    ("top_10", 0, 10),
    ("rank_11_25", 10, 25),
    ("rank_26_50", 25, 50),
    ("rest", 50, None)
)

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

def future_index(timestamps, index, seconds, tolerance=90, max_gap=120):
    target = timestamps[index] + seconds
    pos = bisect_left(timestamps, target, index + 1)
    candidates = [i for i in (pos - 1, pos) if index < i < len(timestamps)]
    if not candidates: return None

    future = min(candidates, key=lambda i: abs(timestamps[i] - target))
    if abs(timestamps[future] - target) > tolerance: return None
    if any(timestamps[i] - timestamps[i - 1] > max_gap for i in range(index + 1, future + 1)): return None
    return future

def metrics(current, future):
    elapsed_min = (future.ts - current.ts) / 60
    price = abs(future.mark_price / current.mark_price - 1) if current.mark_price and future.mark_price else None
    current_oi, future_oi = current.open_interest_notional, future.open_interest_notional
    oi = abs(future_oi / current_oi - 1) if current_oi and future_oi else None
    volume = max(0, future.day_notional_volume - current.day_notional_volume) / elapsed_min
    return price, volume, oi

def group_metrics(keys, current, future):
    values = [metrics(current[key], future[key]) for key in keys if key in current and key in future]
    result = []

    for i in range(3):
        valid = [value[i] for value in values if value[i] is not None]
        result.append(mean(valid) if valid else None)

    return len(values), tuple(result)

def add_result(results, counts, horizon, group, keys, current, future):
    count, values = group_metrics(keys, current, future)
    if not count: return
    counts[horizon, group] += count

    for metric, value in zip(METRICS, values):
        if value is not None: results[horizon, group, metric].append(value)

def value(results, horizon, group, metric):
    values = results[horizon, group, metric]
    return median(values) if values else None

def fmt(metric, number):
    if number is None: return "-"
    if metric == "volume": return f"${number:,.0f}/min"
    return f"{number:.3%}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/raw/hyperliquid_universe")
    args = parser.parse_args()

    paths = sorted(Path(args.input).glob("universe_*.jsonl"))
    if not paths: raise SystemExit("no universe files found")

    data = list(snapshots(paths))
    timestamps = [snapshot[0].ts for snapshot in data]

    tracker = MarketActivityTracker()
    window = MarketActivityWindow()
    selector = MarketSelector(MarketSelectorConfig(top_n=10_000))
    states = []

    for snapshot in data:
        rolling = window.update(tracker.update(snapshot))
        states.append(selector.select(rolling))

    results = defaultdict(list)
    counts = defaultdict(int)
    decisions = defaultdict(int)
    next_allowed = defaultdict(float)

    for index, snapshot in enumerate(data):
        candidates = states[index]
        if not candidates: continue

        current = {(row.dex, row.coin): row for row in snapshot}

        for horizon in (5, 15, 30):
            if timestamps[index] < next_allowed[horizon]: continue

            future_i = future_index(timestamps, index, horizon * 60)
            if future_i is None: continue

            future = {(row.dex, row.coin): row for row in data[future_i]}
            decisions[horizon] += 1
            next_allowed[horizon] = timestamps[index] + horizon * 60

            for name, start, end in BUCKETS:
                bucket = candidates[start:end]
                keys = {(row.dex, row.coin) for row in bucket}
                add_result(results, counts, horizon, name, keys, current, future)

            top = candidates[:10]
            warm = {(row.dex, row.coin) for row in top if row.warm}
            cold = {(row.dex, row.coin) for row in top if not row.warm}
            add_result(results, counts, horizon, "top10_warm", warm, current, future)
            add_result(results, counts, horizon, "top10_cold", cold, current, future)

    print(f"files={len(paths)} snapshots={len(data)}")

    for horizon in (5, 15, 30):
        print(f"\n{horizon}m forward — non-overlapping decisions={decisions[horizon]}")
        print("\nRank buckets:")

        for group, _, _ in BUCKETS:
            print(f"{group:<12} market_obs={counts[horizon, group]:<6}", end="")
            for metric in METRICS:
                print(f" {metric}={fmt(metric, value(results, horizon, group, metric))}", end="")
            print()

        print("\nTop 10 vs rest lift:")
        for metric in METRICS:
            top = value(results, horizon, "top_10", metric)
            rest = value(results, horizon, "rest", metric)
            lift = top / rest if top is not None and rest and rest > 0 else None
            print(f"{metric:<8} {lift:.2f}x" if lift is not None else f"{metric:<8} -")

        print("\nTop 10 warm vs cold-start:")
        for group in ("top10_warm", "top10_cold"):
            print(f"{group:<12} market_obs={counts[horizon, group]:<6}", end="")
            for metric in METRICS:
                print(f" {metric}={fmt(metric, value(results, horizon, group, metric))}", end="")
            print()

if __name__ == "__main__":
    main()