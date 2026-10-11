import argparse
import json
import platform
import resource
import sys
import time
from pathlib import Path
from statistics import median

from hlbot.backtest.replay import ReplayBacktester
from hlbot.data.market_data_loader import load_market_data_directory
from hlbot.strategy.engine import StrategyEngine
from hlbot.strategy.signal import NoSignalModel
from hlbot.strategy.specification import StrategySpec


def percentile(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int((len(values) - 1) * p))]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("coin")
    parser.add_argument("--data-dir", default="data/raw/hummingbot_vps")
    parser.add_argument("--runs", type=int, default=10)
    args = parser.parse_args()
    if args.runs < 1: raise ValueError("runs must be positive")

    snapshots, trades = load_market_data_directory(args.data_dir, f"{args.coin}-USD")
    if not snapshots: raise ValueError("no snapshots found")
    engine = StrategyEngine(
        StrategySpec(base_order_notional=100, max_position_notional=1000, max_scale_ins=0),
        NoSignalModel()
    )
    backtester = ReplayBacktester(engine)
    events = len(snapshots) + len(trades)

    backtester.run(snapshots[:100], trades[:100])  # Warm-up

    times = []
    for _ in range(args.runs):
        start = time.perf_counter_ns()
        backtester.run(snapshots, trades)
        times.append((time.perf_counter_ns() - start) / 1e9)

    seconds = median(times)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_mb = rss / (1024 ** 2 if sys.platform == "darwin" else 1024)

    report = {
        "benchmark": "historical_replay",
        "events": events,
        "snapshots": len(snapshots),
        "trades": len(trades),
        "runs": args.runs,
        "median_seconds": seconds,
        "events_per_second": events / seconds,
        "p95_run_seconds": percentile(times, 0.95),
        "p99_run_seconds": percentile(times, 0.99),
        "peak_process_rss_mb": rss_mb,
        "python": platform.python_version(),
        "machine": platform.machine(),
        "system": platform.platform()
    }

    Path("reports").mkdir(exist_ok=True)
    Path("reports/replay_benchmark.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()