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
    price = None
    oi = None

    if current.mark_price and future.mark_price:
        price = abs(future.mark_price / current.mark_price - 1)

    current_oi = current.open_interest_notional
    future_oi = future.open_interest_notional
    if current_oi and future_oi:
        oi = abs(future_oi / current_oi - 1)

    volume = max(0, future.day_notional_volume - current.day_notional_volume) / elapsed_min
    return price, volume, oi

def group_metrics(keys, current, future):
    values = [metrics(current[key], future[key]) for key in keys if key in current and key in future]
    result = []

    for i in range(3):
        metric = [value[i] for value in values if value[i] is not None]
        result.append(mean(metric) if metric else None)

    return tuple(result)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/raw/hyperliquid_universe")
    parser.add_argument("--top-n", type=int, default=10)
    args = parser.parse_args()

    paths = sorted(Path(args.input).glob("universe_*.jsonl"))
    if not paths: raise SystemExit("no universe files found")

    data = list(snapshots(paths))
    timestamps = [snapshot[0].ts for snapshot in data]

    tracker = MarketActivityTracker()
    window = MarketActivityWindow()
    selector = MarketSelector(MarketSelectorConfig(top_n=args.top_n))
    states = []

    for snapshot in data:
        rolling = window.update(tracker.update(snapshot))
        states.append((rolling, selector.select(rolling)))

    results = defaultdict(list)
    valid = defaultdict(int)

    for index, snapshot in enumerate(data):
        rolling, selected = states[index]
        if not selected: continue

        current = {(row.dex, row.coin): row for row in snapshot}
        eligible = {(row.dex, row.coin) for row in rolling if row.active and row.volume_5m > 0}
        selected_keys = {(row.dex, row.coin) for row in selected}
        control_keys = eligible - selected_keys

        for minutes in (5, 15, 30):
            future_i = future_index(timestamps, index, minutes * 60)
            if future_i is None: continue

            future = {(row.dex, row.coin): row for row in data[future_i]}
            selected_values = group_metrics(selected_keys, current, future)
            control_values = group_metrics(control_keys, current, future)

            if any(value is None for value in selected_values + control_values): continue

            valid[minutes] += 1
            for name, values in (("selected", selected_values), ("control", control_values)):
                for metric, value in zip(("price", "volume", "oi"), values):
                    results[minutes, name, metric].append(value)

    print(f"snapshots={len(data)}")

    for minutes in (5, 15, 30):
        print(f"\n{minutes}m forward — valid snapshots={valid[minutes]}")

        for metric in ("price", "volume", "oi"):
            selected = median(results[minutes, "selected", metric])
            control = median(results[minutes, "control", metric])
            lift = selected / control if control > 0 else float("inf")

            if metric == "volume":
                print(f"volume/min   selected=${selected:,.0f} control=${control:,.0f} lift={lift:.2f}x")
            else:
                print(f"{metric:<12} selected={selected:.3%} control={control:.3%} lift={lift:.2f}x")

if __name__ == "__main__":
    main()