import argparse
import time

from hlbot.backtest.performance import summarize_replay
from hlbot.backtest.replay import ReplayBacktester
from hlbot.data.market_data_loader import load_market_data_directory
from hlbot.strategy.engine import StrategyEngine
from hlbot.strategy.signal import NoSignalModel
from hlbot.strategy.specification import StrategySpec

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("coin", choices=("PONS", "CASHCAT", "PURR", "LIT"))
    parser.add_argument("--data-dir", default="data/raw/hummingbot_vps")
    args = parser.parse_args()

    print(f"Loading {args.coin}-USD...")

    snapshots, trades = load_market_data_directory(args.data_dir, f"{args.coin}-USD")

    print(f"Snapshots: {len(snapshots)}")
    print(f"Trades: {len(trades)}")

    if not snapshots:
        print("No snapshots found.")
        return

    spec = StrategySpec(
        base_order_notional=100,
        max_position_notional=1000,
        max_scale_ins=0
    )

    backtester = ReplayBacktester(StrategyEngine(spec, NoSignalModel()))

    start = time.perf_counter()
    result = backtester.run(snapshots, trades)
    elapsed = time.perf_counter() - start
    summary = summarize_replay(result)

    print("\nReplay:")
    print(f"  states evaluated: {result.states_evaluated}")
    print(f"  states skipped:   {result.states_skipped}")
    print(f"  fills:            {summary.fills}")
    print(f"  closed trades:    {summary.closed_trades}")
    print(f"  net PnL:          {summary.net_pnl:.6f}")
    print(f"  runtime:          {elapsed:.3f}s")

if __name__ == "__main__":
    main()