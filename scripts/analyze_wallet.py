import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from hlbot.models.wallet_fill import WalletFill
from hlbot.wallet_analysis.episode_builder import EpisodeBuilder
from hlbot.wallet_analysis.pnl_analysis import analyze_wallet_performance

EPSILON = 1e-9

def load_fills(path: Path) -> list[WalletFill]:
    fills = []

    with open(path) as file:
        for line in file:
            if line.strip(): fills.append(WalletFill(**json.loads(line)))

    return fills

def format_time(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def end_position(fill: WalletFill) -> float | None:
    if fill.start_position is None: return None
    signed_quantity = fill.quantity if fill.side == "buy" else -fill.quantity
    return fill.start_position + signed_quantity

def is_flat(position: float | None) -> bool:
    return position is not None and abs(position) <= EPSILON

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("wallet")
    args = parser.parse_args()

    wallet = args.wallet.lower()
    path = Path("data/processed/wallets") / f"{wallet}_fills.jsonl"

    if not path.exists(): raise FileNotFoundError(f"Wallet data not found: {path}")

    fills = load_fills(path)
    episodes = EpisodeBuilder().build(fills)
    report = analyze_wallet_performance(episodes)

    print(f"Fills: {len(fills)}")
    print(f"Complete perpetual episodes: {len(episodes)}")

    if fills:
        print(f"First fill: {format_time(fills[0].timestamp)}")
        print(f"Last fill:  {format_time(fills[-1].timestamp)}")

    print("\nPerformance:")
    print(f"  Total PnL: {report.total_pnl:.2f}")
    print(f"  Win rate: {report.win_rate:.2%}")
    print(f"  Average episode PnL: {report.average_pnl:.2f}")
    print(f"  Median episode PnL: {report.median_pnl:.2f}")
    print(f"  Best episode: {report.best_pnl:.2f}")
    print(f"  Worst episode: {report.worst_pnl:.2f}")
    print(f"  Max drawdown: {report.max_drawdown:.2f}")
    print(f"  Longest losing streak: {report.longest_losing_streak}")
    print(f"  PnL without top 1%: {report.pnl_without_top_1_pct:.2f}")
    print(f"  PnL without top 5%: {report.pnl_without_top_5_pct:.2f}")

    fills_by_coin = defaultdict(list)
    for fill in fills: fills_by_coin[fill.coin].append(fill)

    episodes_by_coin = Counter(episode.coin for episode in episodes)

    print("\nEpisodes by coin:")
    for coin, count in episodes_by_coin.most_common():
        print(f"  {coin}: {count}")

    print("\nPnL by coin:")
    for coin, pnl in report.pnl_by_coin.items():
        print(f"  {coin}: {pnl:.2f}")

    print("\nPosition diagnostics:")
    for coin, coin_fills in sorted(fills_by_coin.items(), key=lambda item: len(item[1]), reverse=True):
        coin_fills = sorted(coin_fills, key=lambda fill: fill.timestamp)
        first = coin_fills[0]
        last = coin_fills[-1]
        flat_starts = sum(is_flat(fill.start_position) for fill in coin_fills)
        flat_ends = sum(is_flat(end_position(fill)) for fill in coin_fills)

        print(f"\n{coin}")
        print(f"  fills: {len(coin_fills)}")
        print(f"  episodes: {episodes_by_coin[coin]}")
        print(f"  first start position: {first.start_position}")
        print(f"  last end position: {end_position(last)}")
        print(f"  fills starting flat: {flat_starts}")
        print(f"  fills ending flat: {flat_ends}")

if __name__ == "__main__":
    main()