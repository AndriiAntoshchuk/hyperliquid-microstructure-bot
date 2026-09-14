import argparse
import glob
from collections import defaultdict
from pathlib import Path
from statistics import mean

from hlbot.data.coverage import find_coverage_segments, timestamp_has_coverage
from hlbot.data.market_data_loader import load_order_books, load_trades
from hlbot.data.wallet_loader import HyperliquidWalletLoader
from hlbot.research.event_study import DEFAULT_MAX_SNAPSHOT_AGE, DEFAULT_OFFSETS, build_event_study, capture_market_point, sample_inactive_times
from hlbot.wallet_analysis.episode_builder import EpisodeBuilder

COVERAGE_MAX_GAP = 15
COVERAGE_MARGIN = max(abs(offset) for offset in DEFAULT_OFFSETS)

def load_wallet_fills(wallet: str):
    return HyperliquidWalletLoader().load_saved(wallet)

def load_market_data(hummingbot_dir: str):
    book_files = sorted(glob.glob(f"{hummingbot_dir}/data/hyperliquid_perpetual_PONS-USD_order_book_snapshots_*.txt"))
    trade_files = sorted(glob.glob(f"{hummingbot_dir}/data/hyperliquid_perpetual_PONS-USD_trades_*.txt"))

    snapshots = []
    trades = []

    for path in book_files: snapshots.extend(load_order_books(path))
    for path in trade_files: trades.extend(load_trades(path))

    snapshots.sort(key=lambda snapshot: snapshot.exchange_ts)
    trades.sort(key=lambda trade: trade.exchange_ts)

    return snapshots, trades

def summarize_points(study: dict[float, list]) -> dict[int, dict[str, float]]:
    grouped = defaultdict(list)

    for points in study.values():
        for point in points: grouped[point.offset_seconds].append(point)

    result = {}

    for offset, points in grouped.items():
        result[offset] = {
            "count": len(points),
            "spread_bps": mean(point.spread_bps for point in points),
            "imbalance_1": mean(point.imbalance_1 for point in points),
            "imbalance_5": mean(point.imbalance_5 for point in points),
            "weighted_imbalance_5": mean(point.weighted_imbalance_5 for point in points),
            "trade_flow_5s": mean(point.trade_flow_5s for point in points),
            "volatility_10s": mean(point.volatility_10s for point in points),
            "bid_liquidity_10bps": mean(point.bid_liquidity_10bps for point in points),
            "ask_liquidity_10bps": mean(point.ask_liquidity_10bps for point in points)
        }

    return result

def build_inactive_study(event_times: list[float], snapshots, trades):
    result = {}

    for event_ts in event_times:
        points = []

        for offset in DEFAULT_OFFSETS:
            point = capture_market_point(event_ts, offset, snapshots, trades, DEFAULT_MAX_SNAPSHOT_AGE)
            if point is not None: points.append(point)

        result[event_ts] = points

    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("wallet")
    parser.add_argument("--hummingbot-dir", default=str(Path.home() / "Documents" / "Hummingbot"))
    args = parser.parse_args()

    fills = load_wallet_fills(args.wallet)
    episodes = [episode for episode in EpisodeBuilder().build(fills) if episode.coin == "PONS"]
    snapshots, trades = load_market_data(args.hummingbot_dir)

    print(f"PONS episodes: {len(episodes)}")
    print(f"Order-book snapshots: {len(snapshots)}")
    print(f"Trades: {len(trades)}")

    if not snapshots:
        print("No usable PONS order-book snapshots found.")
        return

    market_start = snapshots[0].exchange_ts
    market_end = snapshots[-1].exchange_ts
    overlapping = [episode for episode in episodes if market_start <= episode.start_ts <= market_end]

    segments = find_coverage_segments(snapshots, COVERAGE_MAX_GAP)
    covered = [episode for episode in overlapping if timestamp_has_coverage(episode.start_ts, segments, COVERAGE_MARGIN)]

    print(f"Market data range: {market_start:.3f} -> {market_end:.3f}")
    print(f"Coverage segments: {len(segments)}")
    print(f"Date-overlapping PONS episodes: {len(overlapping)}")
    print(f"Coverage-qualified PONS episodes: {len(covered)}")

    if not covered:
        print("No PONS episodes have continuous market coverage around entry.")
        return

    active_study = build_event_study(covered, snapshots, trades)

    inactive_times = sample_inactive_times(
        covered,
        snapshots,
        count=len(covered),
        exclusion_seconds=60,
        coverage_segments=segments,
        coverage_margin_seconds=COVERAGE_MARGIN
    )

    inactive_study = build_inactive_study(inactive_times, snapshots, trades)

    active_summary = summarize_points(active_study)
    inactive_summary = summarize_points(inactive_study)

    print("\nActive vs inactive:")

    for offset in DEFAULT_OFFSETS:
        active = active_summary.get(offset)
        inactive = inactive_summary.get(offset)

        if active is None or inactive is None: continue

        print(f"\nOffset {offset:+d}s")
        print(f"  active count: {active['count']}")
        print(f"  inactive count: {inactive['count']}")
        print(f"  spread bps: {active['spread_bps']:.4f} vs {inactive['spread_bps']:.4f}")
        print(f"  imbalance 1: {active['imbalance_1']:.4f} vs {inactive['imbalance_1']:.4f}")
        print(f"  imbalance 5: {active['imbalance_5']:.4f} vs {inactive['imbalance_5']:.4f}")
        print(f"  weighted imbalance 5: {active['weighted_imbalance_5']:.4f} vs {inactive['weighted_imbalance_5']:.4f}")
        print(f"  trade flow 5s: {active['trade_flow_5s']:.4f} vs {inactive['trade_flow_5s']:.4f}")
        print(f"  volatility 10s: {active['volatility_10s']:.6f} vs {inactive['volatility_10s']:.6f}")

if __name__ == "__main__":
    main()