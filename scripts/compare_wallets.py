import argparse
import json
from pathlib import Path

from hlbot.models.wallet_fill import WalletFill
from hlbot.wallet_analysis.episode_builder import EpisodeBuilder
from hlbot.wallet_analysis.wallet_comparison import compare_wallets

def load_fills(wallet: str) -> list[WalletFill]:
    path = Path("data/processed/wallets") / f"{wallet.lower()}_fills.jsonl"

    if not path.exists(): raise FileNotFoundError(f"Wallet data not found: {path}")

    fills = []

    with open(path) as file:
        for line in file:
            if line.strip(): fills.append(WalletFill(**json.loads(line)))

    return fills

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("wallets", nargs="+")
    args = parser.parse_args()

    wallet_episodes = {}

    for wallet in args.wallets:
        fills = load_fills(wallet)
        wallet_episodes[wallet.lower()] = EpisodeBuilder().build(fills)

    comparison = compare_wallets(wallet_episodes)

    for summary in comparison.wallets:
        print(f"\nWallet: {summary.wallet}")
        print(f"  Episodes: {summary.number_of_episodes}")
        print(f"  Total PnL: {summary.total_pnl:.2f}")
        print(f"  Win rate: {summary.win_rate:.2%}")
        print(f"  Average duration: {summary.average_duration:.2f}s")
        print(f"  Median duration: {summary.median_duration:.2f}s")
        print(f"  Average fills per episode: {summary.average_fills_per_episode:.2f}")
        print(f"  Median fills per episode: {summary.median_fills_per_episode:.2f}")
        print(f"  Average max position notional: ${summary.average_max_position_notional:.2f}")
        print(f"  Long episodes: {summary.long_episodes}")
        print(f"  Short episodes: {summary.short_episodes}")
        print(f"  Coins: {', '.join(summary.coins) if summary.coins else 'None'}")
        print(f"  Active hours UTC: {summary.active_hours_utc}")

    print("\nPairwise overlap:")

    for pair in comparison.pairwise:
        print(f"\n{pair.wallet_a} <-> {pair.wallet_b}")
        print(f"  Common coins: {pair.common_coins}")
        print(f"  Common active hours UTC: {pair.common_active_hours_utc}")

if __name__ == "__main__":
    main()