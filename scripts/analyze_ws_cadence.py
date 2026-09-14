import argparse
from statistics import mean, median

from hlbot.data.hyperliquid_ws_loader import load_ws_market_data

def percentile(values: list[float], fraction: float) -> float:
    if not values: return 0.0

    values = sorted(values)
    index = round((len(values) - 1) * fraction)
    return values[index]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--coin", default="PONS")
    parser.add_argument("--data-dir", default="data/raw/hyperliquid_ws")
    args = parser.parse_args()

    snapshots, trades = load_ws_market_data(args.data_dir, args.coin)

    print(f"Coin: {args.coin}")
    print(f"Snapshots: {len(snapshots)}")
    print(f"Trades: {len(trades)}")

    if len(snapshots) < 2:
        print("Not enough snapshots to calculate cadence.")
        return

    exchange_gaps = [
        current.exchange_ts - previous.exchange_ts
        for previous, current in zip(snapshots, snapshots[1:])
        if current.exchange_ts >= previous.exchange_ts
    ]

    local_gaps = [
        current.local_ts - previous.local_ts
        for previous, current in zip(snapshots, snapshots[1:])
        if current.local_ts >= previous.local_ts
    ]

    delays = [
        snapshot.local_ts - snapshot.exchange_ts
        for snapshot in snapshots
    ]

    print("\nExchange snapshot gaps:")
    print(f"  observations: {len(exchange_gaps)}")
    print(f"  min: {min(exchange_gaps):.3f}s")
    print(f"  p25: {percentile(exchange_gaps, 0.25):.3f}s")
    print(f"  median: {median(exchange_gaps):.3f}s")
    print(f"  mean: {mean(exchange_gaps):.3f}s")
    print(f"  p75: {percentile(exchange_gaps, 0.75):.3f}s")
    print(f"  p90: {percentile(exchange_gaps, 0.90):.3f}s")
    print(f"  p99: {percentile(exchange_gaps, 0.99):.3f}s")
    print(f"  max: {max(exchange_gaps):.3f}s")

    print("\nGap frequencies:")
    print(f"  <= 1s: {sum(gap <= 1 for gap in exchange_gaps) / len(exchange_gaps):.1%}")
    print(f"  <= 2s: {sum(gap <= 2 for gap in exchange_gaps) / len(exchange_gaps):.1%}")
    print(f"  <= 5s: {sum(gap <= 5 for gap in exchange_gaps) / len(exchange_gaps):.1%}")
    print(f"  <= 6s: {sum(gap <= 6 for gap in exchange_gaps) / len(exchange_gaps):.1%}")
    print(f"  > 10s: {sum(gap > 10 for gap in exchange_gaps) / len(exchange_gaps):.1%}")

    print("\nLocal receive gaps:")
    print(f"  median: {median(local_gaps):.3f}s")
    print(f"  p90: {percentile(local_gaps, 0.90):.3f}s")
    print(f"  max: {max(local_gaps):.3f}s")

    print("\nExchange -> local receive delay:")
    print(f"  median: {median(delays) * 1000:.1f}ms")
    print(f"  p90: {percentile(delays, 0.90) * 1000:.1f}ms")
    print(f"  p99: {percentile(delays, 0.99) * 1000:.1f}ms")
    print(f"  max: {max(delays) * 1000:.1f}ms")

if __name__ == "__main__":
    main()