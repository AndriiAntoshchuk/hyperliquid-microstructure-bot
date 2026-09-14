import argparse
from collections import defaultdict
from statistics import median

from hlbot.data.wallet_loader import HyperliquidWalletLoader
from hlbot.wallet_analysis.episode_builder import EpisodeBuilder
from hlbot.wallet_analysis.position_sizing import build_order_executions

def percentile(values: list[float], fraction: float) -> float:
    if not values: return 0.0

    values = sorted(values)
    index = round((len(values) - 1) * fraction)
    return values[index]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("wallet")
    args = parser.parse_args()

    fills = HyperliquidWalletLoader().load_saved(args.wallet)
    episodes = EpisodeBuilder().build(fills)

    by_step = defaultdict(list)
    by_coin = defaultdict(list)
    consecutive_ratios = []

    for episode in episodes:
        orders = build_order_executions(episode)
        entry_orders = [order for order in orders if order.change_type in {"entry", "scale_in"}]

        if not entry_orders: continue

        initial = entry_orders[0].notional

        if initial <= 0: continue

        for index, order in enumerate(entry_orders):
            by_step[index].append(order.notional / initial)
            by_coin[episode.coin].append(order.notional / initial)

        for previous, current in zip(entry_orders, entry_orders[1:]):
            if previous.notional > 0:
                consecutive_ratios.append(current.notional / previous.notional)

    print("Scale-in order size relative to initial order:")

    for index in sorted(by_step)[:10]:
        values = by_step[index]

        print(
            f"  order {index + 1}: "
            f"n={len(values)} | "
            f"median {median(values):.2f}x | "
            f"p25 {percentile(values, 0.25):.2f}x | "
            f"p75 {percentile(values, 0.75):.2f}x"
        )

    print("\nConsecutive entry-order size ratios:")

    if consecutive_ratios:
        print(f"  observations: {len(consecutive_ratios)}")
        print(f"  median: {median(consecutive_ratios):.2f}x")
        print(f"  p25: {percentile(consecutive_ratios, 0.25):.2f}x")
        print(f"  p75: {percentile(consecutive_ratios, 0.75):.2f}x")

    print("\nMedian entry-order ratio by coin:")

    for coin, values in sorted(by_coin.items(), key=lambda item: len(item[1]), reverse=True):
        print(f"  {coin}: n={len(values)} | median {median(values):.2f}x")

if __name__ == "__main__":
    main()