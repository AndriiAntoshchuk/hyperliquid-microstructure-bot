import argparse
from pathlib import Path

from hlbot.data.coverage import find_coverage_segments, timestamp_has_coverage
from hlbot.research.event_study import build_event_study
from hlbot.research.momentum_mean_reversion import analyze_study, summarize_observations
from hlbot.wallet_analysis.episode_builder import EpisodeBuilder
from run_event_study import load_market_data, load_wallet_fills

COVERAGE_MAX_GAP = 15
COVERAGE_MARGIN = 30
WINDOWS = ((5, 5), (10, 10), (30, 30))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("wallet")
    parser.add_argument("--hummingbot-dir", default=str(Path.home() / "Documents" / "Hummingbot"))
    args = parser.parse_args()

    fills = load_wallet_fills(args.wallet)
    episodes = [episode for episode in EpisodeBuilder().build(fills) if episode.coin == "PONS"]
    snapshots, trades = load_market_data(args.hummingbot_dir)

    if not snapshots:
        print("No market data found.")
        return

    segments = find_coverage_segments(snapshots, COVERAGE_MAX_GAP)
    covered = [
        episode
        for episode in episodes
        if timestamp_has_coverage(episode.start_ts, segments, COVERAGE_MARGIN)
    ]

    print(f"PONS episodes: {len(episodes)}")
    print(f"Coverage-qualified episodes: {len(covered)}")

    if not covered:
        print("No episodes have sufficient market-data coverage.")
        return

    study = build_event_study(covered, snapshots, trades)

    for lookback, horizon in WINDOWS:
        observations = analyze_study(
            covered,
            study,
            lookback_seconds=lookback,
            horizon_seconds=horizon
        )

        summary = summarize_observations(observations)

        print(f"\nWindow: -{lookback}s / +{horizon}s")
        print(f"  observations: {summary.observations}")
        print(f"  momentum entries: {summary.momentum_entries}")
        print(f"  mean-reversion entries: {summary.mean_reversion_entries}")
        print(f"  neutral entries: {summary.neutral_entries}")
        print(f"  momentum fraction: {summary.momentum_fraction:.2%}")
        print(f"  mean-reversion fraction: {summary.mean_reversion_fraction:.2%}")
        print(f"  avg signed pre-return: {summary.average_signed_pre_return_pct:.4f}%")
        print(f"  avg signed post-return: {summary.average_signed_post_return_pct:.4f}%")
        print(f"  momentum avg post-return: {summary.momentum_average_post_return_pct:.4f}%")
        print(f"  mean-reversion avg post-return: {summary.mean_reversion_average_post_return_pct:.4f}%")

if __name__ == "__main__":
    main()