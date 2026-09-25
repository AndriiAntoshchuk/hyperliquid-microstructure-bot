import argparse
import random
from collections import defaultdict
from dataclasses import dataclass
from statistics import median

from hlbot.data.coverage import find_coverage_segments, timestamp_has_coverage
from hlbot.data.hyperliquid_ws_loader import load_ws_market_data
from hlbot.data.market_data_loader import load_market_data_directory
from hlbot.data.wallet_loader import HyperliquidWalletLoader
from hlbot.research.event_study import DEFAULT_OFFSETS, sample_inactive_times
from hlbot.strategy.market_state import MarketStateBuilder
from hlbot.wallet_analysis.episode_builder import EpisodeBuilder
from hlbot.wallet_analysis.position_sizing import build_order_executions

DEFAULT_WALLETS = (
    "0x0526345bf8e09eb32256008c2844c8949ee3bb9a",
    "0x3089602b74dd5a7a8fdf78812ef1278df1d20e83",
    "0x37c2a0912e44ea4c293866dfa3735d58ef1ecb4f",
    "0xa046c1c83a3b295ca99bb9efdd19836b12409373"
)

MARKETS = ("PONS", "CASHCAT", "PURR", "LIT")

SOURCE_DIRS = {
    "deep": "data/raw/hummingbot_vps",
    "fast": "data/raw/hyperliquid_ws_fast"
}

SOURCE_MAX_GAP = {
    "deep": 15.0,
    "fast": 2.0
}

SOURCE_MAX_AGE = {
    "deep": 15.0,
    "fast": 2.0
}

COVERAGE_MARGIN = max(abs(offset) for offset in DEFAULT_OFFSETS)

@dataclass(frozen=True)
class StudyPoint:
    offset: int
    spread_bps: float
    volatility_10s: float
    bid_liquidity_10bps: float
    ask_liquidity_10bps: float
    aligned_imbalance_1: float
    aligned_imbalance_5: float
    aligned_weighted_imbalance_5: float
    aligned_microprice_deviation_bps: float
    aligned_trade_flow_5s: float
    aligned_return_5s: float
    aligned_return_30s: float
    aligned_liquidity_imbalance_10bps: float

def load_market_data(source: str, data_dir: str, coin: str):
    if source == "fast": return load_ws_market_data(data_dir, coin)
    return load_market_data_directory(data_dir, f"{coin}-USD")

def direction_sign(direction: str) -> float:
    if direction == "long": return 1.0
    if direction == "short": return -1.0
    raise ValueError(f"Unsupported direction: {direction}")

def liquidity_imbalance(bid: float, ask: float) -> float:
    total = bid + ask
    return 0.0 if total == 0 else (bid - ask) / total

def build_study(events: list[tuple[float, str]], builder: MarketStateBuilder):
    grouped = defaultdict(list)

    for event_ts, direction in events:
        sign = direction_sign(direction)

        for offset in DEFAULT_OFFSETS:
            state = builder.build(event_ts + offset)
            if state is None: continue

            grouped[offset].append(
                StudyPoint(
                    offset=offset,
                    spread_bps=state.spread_bps,
                    volatility_10s=state.volatility_10s,
                    bid_liquidity_10bps=state.bid_liquidity_10bps,
                    ask_liquidity_10bps=state.ask_liquidity_10bps,
                    aligned_imbalance_1=state.imbalance_1 * sign,
                    aligned_imbalance_5=state.imbalance_5 * sign,
                    aligned_weighted_imbalance_5=state.weighted_imbalance_5 * sign,
                    aligned_microprice_deviation_bps=state.microprice_deviation_bps * sign,
                    aligned_trade_flow_5s=state.trade_flow_5s * sign,
                    aligned_return_5s=state.return_5s * sign,
                    aligned_return_30s=state.return_30s * sign,
                    aligned_liquidity_imbalance_10bps=liquidity_imbalance(
                        state.bid_liquidity_10bps,
                        state.ask_liquidity_10bps
                    ) * sign
                )
            )

    return grouped

def feature_median(points: list[StudyPoint], name: str) -> float:
    return median(getattr(point, name) for point in points)

def print_feature(name: str, active: list[StudyPoint], inactive: list[StudyPoint]):
    active_value = feature_median(active, name)
    inactive_value = feature_median(inactive, name)

    print(
        f"  {name}: "
        f"{active_value:+.6f} vs {inactive_value:+.6f} "
        f"| diff={active_value - inactive_value:+.6f}"
    )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=("deep", "fast"), default="fast")
    parser.add_argument("--data-dir")
    parser.add_argument("--coin", choices=MARKETS, default="PONS")
    parser.add_argument("--wallets", nargs="+", default=DEFAULT_WALLETS)
    parser.add_argument("--inactive-multiplier", type=int, default=20)
    args = parser.parse_args()

    if args.inactive_multiplier <= 0:
        raise ValueError("inactive-multiplier must be positive")

    data_dir = args.data_dir or SOURCE_DIRS[args.source]
    max_gap = SOURCE_MAX_GAP[args.source]
    max_age = SOURCE_MAX_AGE[args.source]

    loader = HyperliquidWalletLoader()
    episodes = []

    for wallet in args.wallets:
        fills = loader.load_saved(wallet)

        episodes.extend(
            episode
            for episode in EpisodeBuilder().build(fills)
            if episode.coin == args.coin
        )

    episodes.sort(key=lambda episode: episode.start_ts)
    snapshots, trades = load_market_data(args.source, data_dir, args.coin)

    print(f"Market: {args.coin}")
    print(f"Source: {args.source}")
    print(f"Historical episodes: {len(episodes)}")
    print(f"Snapshots: {len(snapshots)}")
    print(f"Trades: {len(trades)}")

    if not snapshots:
        print("No market data.")
        return

    market_start = snapshots[0].exchange_ts
    market_end = snapshots[-1].exchange_ts
    segments = find_coverage_segments(snapshots, max_gap)

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
            COVERAGE_MARGIN
        )
    ]

    longs = sum(episode.direction == "long" for episode in covered)
    shorts = sum(episode.direction == "short" for episode in covered)

    print(f"Date-overlapping episodes: {len(overlapping)}")
    print(f"Coverage-qualified episodes: {len(covered)}")
    print(f"LONG episodes: {longs}")
    print(f"SHORT episodes: {shorts}")
    print(f"Coverage segments: {len(segments)}")

    if not covered:
        print("No coverage-qualified episodes.")
        return

    builder = MarketStateBuilder(snapshots, trades, max_age)

    active_events = [
        (episode.start_ts, episode.direction)
        for episode in covered
    ]

    active_study = build_study(active_events, builder)

    inactive_times = sample_inactive_times(
        covered,
        snapshots,
        count=len(covered) * args.inactive_multiplier,
        exclusion_seconds=60,
        coverage_segments=segments,
        coverage_margin_seconds=COVERAGE_MARGIN
    )

    control_directions = [
        episode.direction
        for episode in covered
        for _ in range(args.inactive_multiplier)
    ]

    random.Random(42).shuffle(control_directions)

    inactive_events = list(
        zip(
            inactive_times,
            control_directions[:len(inactive_times)]
        )
    )

    inactive_study = build_study(inactive_events, builder)

    print(f"Inactive control times: {len(inactive_times)}")
    print("\nDirection-aligned active vs inactive medians:")

    signed_features = (
        "aligned_imbalance_1",
        "aligned_imbalance_5",
        "aligned_weighted_imbalance_5",
        "aligned_microprice_deviation_bps",
        "aligned_trade_flow_5s",
        "aligned_return_5s",
        "aligned_return_30s",
        "aligned_liquidity_imbalance_10bps"
    )

    raw_features = (
        "spread_bps",
        "volatility_10s",
        "bid_liquidity_10bps",
        "ask_liquidity_10bps"
    )

    for offset in DEFAULT_OFFSETS:
        active = active_study[offset]
        inactive = inactive_study[offset]

        if not active or not inactive: continue

        print(f"\nOffset {offset:+d}s")
        print(f"  active count: {len(active)}")
        print(f"  inactive count: {len(inactive)}")

        print("  directional:")
        for feature in signed_features:
            print_feature(feature, active, inactive)

        print("  raw:")
        for feature in raw_features:
            print_feature(feature, active, inactive)

    action_events = defaultdict(list)

    for episode in covered:
        for order in build_order_executions(episode):
            if not timestamp_has_coverage(order.first_ts, segments, COVERAGE_MARGIN): continue

            if order.change_type == "scale_in":
                action_events["SCALE_IN"].append((order.first_ts, episode.direction))
            elif order.change_type == "scale_out":
                action = "FINAL_EXIT" if order.end_position is not None and abs(order.end_position) <= 1e-9 else "SCALE_OUT"
                action_events[action].append((order.first_ts, episode.direction))

    print("\nPosition-change events vs same inactive control:")

    for action in ("SCALE_IN", "SCALE_OUT", "FINAL_EXIT"):
        events = action_events[action]
        if not events: continue

        study = build_study(events, builder)
        print(f"\n===== {action} | events={len(events)} =====")

        for offset in DEFAULT_OFFSETS:
            active = study[offset]
            inactive = inactive_study[offset]
            if not active or not inactive: continue

            print(f"\nOffset {offset:+d}s")
            print(f"  active count: {len(active)}")
            print(f"  inactive count: {len(inactive)}")

            print("  directional:")
            for feature in signed_features:
                print_feature(feature, active, inactive)

            print("  raw:")
            for feature in raw_features:
                print_feature(feature, active, inactive)

if __name__ == "__main__":
    main()