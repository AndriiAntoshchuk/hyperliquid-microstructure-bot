import argparse
from collections import defaultdict
from datetime import datetime, timezone

from hlbot.data.coverage import find_coverage_segments, timestamp_has_coverage
from hlbot.data.market_data_loader import load_market_data_directory
from hlbot.data.wallet_loader import HyperliquidWalletLoader
from hlbot.wallet_analysis.episode_builder import EpisodeBuilder

COVERAGE_MAX_GAP = 15
COVERAGE_MARGIN = 30

DEFAULT_WALLETS = [
    "0x0526345bf8e09eb32256008c2844c8949ee3bb9a",
    "0x3089602b74dd5a7a8fdf78812ef1278df1d20e83",
    "0x37c2a0912e44ea4c293866dfa3735d58ef1ecb4f",
    "0xa046c1c83a3b295ca99bb9efdd19836b12409373"
]

MARKETS = ("PONS", "CASHCAT", "PURR", "LIT")

def utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir",
        default="data/raw/hummingbot_vps"
    )
    parser.add_argument(
        "--wallets",
        nargs="+",
        default=DEFAULT_WALLETS
    )
    args = parser.parse_args()

    loader = HyperliquidWalletLoader()
    episodes_by_wallet = {}

    for wallet in args.wallets:
        fills = loader.load_saved(wallet)
        episodes_by_wallet[wallet] = EpisodeBuilder().build(fills)

    total_covered = 0

    for coin in MARKETS:
        trading_pair = f"{coin}-USD"
        snapshots, trades = load_market_data_directory(
            args.data_dir,
            trading_pair
        )

        print()
        print(f"===== {coin} =====")
        print(f"Snapshots: {len(snapshots)}")
        print(f"Trades: {len(trades)}")

        if not snapshots:
            print("No market data.")
            continue

        market_start = snapshots[0].exchange_ts
        market_end = snapshots[-1].exchange_ts
        segments = find_coverage_segments(
            snapshots,
            max_gap_seconds=COVERAGE_MAX_GAP
        )

        print(f"Market start: {utc(market_start)}")
        print(f"Market end:   {utc(market_end)}")
        print(f"Coverage segments: {len(segments)}")

        coin_total = 0
        coin_overlap = 0
        coin_covered = 0
        covered_by_day = defaultdict(int)

        for wallet in args.wallets:
            episodes = [
                episode
                for episode in episodes_by_wallet[wallet]
                if episode.coin == coin
            ]

            overlapping = [
                episode
                for episode in episodes
                if market_start <= episode.start_ts <= market_end
            ]

            covered = [
                episode
                for episode in overlapping
                if timestamp_has_coverage(
                    episode.start_ts,
                    segments,
                    margin_seconds=COVERAGE_MARGIN
                )
            ]

            coin_total += len(episodes)
            coin_overlap += len(overlapping)
            coin_covered += len(covered)

            for episode in covered:
                day = datetime.fromtimestamp(
                    episode.start_ts,
                    timezone.utc
                ).strftime("%Y-%m-%d")

                covered_by_day[day] += 1

            print(
                f"{wallet[:10]}... "
                f"total={len(episodes)} | "
                f"date-overlap={len(overlapping)} | "
                f"coverage-qualified={len(covered)}"
            )

        print()
        print(f"{coin} totals:")
        print(f"  historical episodes: {coin_total}")
        print(f"  date-overlap: {coin_overlap}")
        print(f"  coverage-qualified: {coin_covered}")

        if covered_by_day:
            print("  qualified by UTC day:")

            for day, count in sorted(covered_by_day.items()):
                print(f"    {day}: {count}")

        total_covered += coin_covered

    print()
    print("===== ALL MARKETS =====")
    print(f"Coverage-qualified episodes: {total_covered}")

if __name__ == "__main__":
    main()