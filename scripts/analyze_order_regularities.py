import argparse
from collections import defaultdict
from statistics import mean, median, pstdev

from hlbot.data.wallet_loader import HyperliquidWalletLoader
from hlbot.wallet_analysis.episode_builder import EpisodeBuilder
from hlbot.wallet_analysis.position_sizing import build_order_executions

def coefficient_of_variation(values: list[float]) -> float:
    if len(values) < 2: return 0.0

    avg = mean(values)
    return 0.0 if avg == 0 else pstdev(values) / avg

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("wallet")
    args = parser.parse_args()

    fills = HyperliquidWalletLoader().load_saved(args.wallet)
    episodes = EpisodeBuilder().build(fills)

    all_cv = []
    later_to_initial = []
    by_coin = defaultdict(list)

    for episode in episodes:
        orders = build_order_executions(episode)
        entry_orders = [order for order in orders if order.change_type in {"entry", "scale_in"}]

        if len(entry_orders) < 2: continue

        initial = entry_orders[0].notional
        later = [order.notional for order in entry_orders[1:]]

        if initial <= 0 or not later: continue

        cv = coefficient_of_variation(later)
        ratio = median(later) / initial

        all_cv.append(cv)
        later_to_initial.append(ratio)
        by_coin[episode.coin].append((cv, ratio))

    print(f"Episodes with multiple entry orders: {len(all_cv)}")

    if all_cv:
        print(f"Median later-order CV: {median(all_cv):.3f}")
        print(f"Median later/initial ratio: {median(later_to_initial):.2f}x")
        print(f"Later orders CV <= 10%: {sum(value <= 0.10 for value in all_cv) / len(all_cv):.1%}")
        print(f"Later orders CV <= 25%: {sum(value <= 0.25 for value in all_cv) / len(all_cv):.1%}")

    print("\nBy coin:")

    for coin, values in sorted(by_coin.items(), key=lambda item: len(item[1]), reverse=True):
        cvs = [value[0] for value in values]
        ratios = [value[1] for value in values]

        print(
            f"  {coin}: "
            f"n={len(values)} | "
            f"later CV {median(cvs):.3f} | "
            f"later/initial {median(ratios):.2f}x"
        )

if __name__ == "__main__":
    main()