import argparse
from collections import defaultdict
from statistics import mean, median

from hlbot.data.wallet_loader import HyperliquidWalletLoader
from hlbot.wallet_analysis.episode_builder import EpisodeBuilder
from hlbot.wallet_analysis.position_sizing import analyze_position_sizing, summarize_position_sizing

def percentile(values: list[float], fraction: float) -> float:
    if not values: return 0.0

    values = sorted(values)
    index = round((len(values) - 1) * fraction)
    return values[index]

def print_summary(name: str, observations) -> None:
    summary = summarize_position_sizing(observations)
    initial = [item.initial_entry_notional for item in observations]
    maximum = [item.max_position_notional for item in observations]
    ratios = [item.scale_ratio for item in observations]
    orders = [item.number_of_orders for item in observations]
    entry_fills = [item.initial_entry_fill_count for item in observations]

    print(f"\n{name}")
    print(f"  episodes: {summary.episodes}")
    print(f"  avg initial order notional: ${summary.average_initial_entry_notional:,.2f}")
    print(f"  median initial order notional: ${summary.median_initial_entry_notional:,.2f}")
    print(f"  initial order p25: ${percentile(initial, 0.25):,.2f}")
    print(f"  initial order p75: ${percentile(initial, 0.75):,.2f}")
    print(f"  avg max position notional: ${summary.average_max_position_notional:,.2f}")
    print(f"  median max position notional: ${summary.median_max_position_notional:,.2f}")
    print(f"  max position p25: ${percentile(maximum, 0.25):,.2f}")
    print(f"  max position p75: ${percentile(maximum, 0.75):,.2f}")
    print(f"  avg scale ratio: {summary.average_scale_ratio:.2f}x")
    print(f"  median scale ratio: {median(ratios):.2f}x")
    print(f"  scale ratio p75: {percentile(ratios, 0.75):.2f}x")
    print(f"  scaled-in episodes: {summary.scaled_in_fraction:.2%}")
    print(f"  avg orders per episode: {summary.average_orders_per_episode:.2f}")
    print(f"  median orders per episode: {median(orders):.1f}")
    print(f"  avg scale-in orders: {summary.average_scale_in_count:.2f}")
    print(f"  avg scale-out orders: {summary.average_scale_out_count:.2f}")
    print(f"  median fills in initial order: {median(entry_fills):.1f}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("wallet")
    args = parser.parse_args()

    fills = HyperliquidWalletLoader().load_saved(args.wallet)

    if not fills:
        print("No saved wallet fills found.")
        return

    episodes = EpisodeBuilder().build(fills)
    observations = analyze_position_sizing(episodes)

    print(f"Wallet: {args.wallet.lower()}")
    print(f"Stored unique fills: {len(fills)}")
    print(f"Complete perpetual episodes: {len(episodes)}")

    print_summary("Overall", observations)

    grouped = defaultdict(list)

    for observation in observations:
        grouped[observation.coin].append(observation)

    print("\nBy coin:")

    for coin, items in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True):
        initial = [item.initial_entry_notional for item in items]
        maximum = [item.max_position_notional for item in items]
        ratios = [item.scale_ratio for item in items]
        orders = [item.number_of_orders for item in items]

        print(
            f"  {coin}: "
            f"{len(items)} eps | "
            f"initial ${median(initial):,.2f} | "
            f"max ${median(maximum):,.2f} | "
            f"ratio {median(ratios):.2f}x | "
            f"orders {median(orders):.1f} | "
            f"scaled {sum(item.scaled_in for item in items) / len(items):.1%}"
        )

if __name__ == "__main__":
    main()