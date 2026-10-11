import argparse
from datetime import datetime, timezone

from hlbot.backtest.performance import summarize_replay
from hlbot.backtest.plotting import save_backtest_charts
from hlbot.backtest.replay import ReplayBacktester
from hlbot.data.hyperliquid_ws_loader import load_ws_market_data
from hlbot.data.market_data_loader import load_market_data_directory
from hlbot.strategy.engine import StrategyEngine
from hlbot.strategy.market_state import MarketStateBuilder
from hlbot.strategy.signal import MarketState, SignalDecision, SignalDirection
from hlbot.strategy.specification import StrategySpec

COINS = ("PONS", "CASHCAT", "PURR", "LIT")
SOURCE_DIRS = {"deep": "data/raw/hummingbot_vps", "fast": "data/raw/hyperliquid_ws_fast"}
SOURCE_MAX_AGE = {"deep": 15.0, "fast": 2.0}

class SingleEntrySignal:
    def __init__(self, entry_ts: float):
        self.entry_ts = entry_ts

    def evaluate(self, state: MarketState) -> SignalDecision:
        if state.timestamp == self.entry_ts: return SignalDecision(SignalDirection.LONG, 1.0, "controlled replay entry")
        return SignalDecision(SignalDirection.NONE, 0.0, "no signal")

def utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()

def load_data(source: str, data_dir: str, coin: str):
    if source == "fast": return load_ws_market_data(data_dir, coin)
    return load_market_data_directory(data_dir, f"{coin}-USD")

def find_entry_timestamp(snapshots, trades, holding_seconds: float, max_snapshot_age: float) -> float:
    builder = MarketStateBuilder(snapshots, trades, max_snapshot_age)

    for index, snapshot in enumerate(snapshots):
        if builder.build(snapshot.exchange_ts) is None: continue

        target_ts = snapshot.exchange_ts + holding_seconds
        previous = snapshot

        for future in snapshots[index + 1:]:
            if future.exchange_ts - previous.exchange_ts > max_snapshot_age: break
            if future.exchange_ts >= target_ts: return snapshot.exchange_ts
            previous = future

    raise RuntimeError("No suitable continuous replay window found")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("coin", choices=COINS)
    parser.add_argument("--source", choices=("deep", "fast"), default="deep")
    parser.add_argument("--data-dir")
    parser.add_argument("--notional", type=float, default=1000)
    parser.add_argument("--holding-seconds", type=float, default=30)
    parser.add_argument("--fee-bps", type=float, default=0)
    parser.add_argument("--liquidity-fraction", type=float)
    args = parser.parse_args()

    data_dir = args.data_dir or SOURCE_DIRS[args.source]
    max_snapshot_age = SOURCE_MAX_AGE[args.source]
    snapshots, trades = load_data(args.source, data_dir, args.coin)
    if not snapshots: raise RuntimeError(f"No {args.coin} snapshots found")

    entry_ts = find_entry_timestamp(snapshots, trades, args.holding_seconds, max_snapshot_age)

    spec = StrategySpec(
        base_order_notional=args.notional,
        max_position_notional=args.notional,
        max_scale_ins=0,
        max_holding_seconds=args.holding_seconds,
        max_visible_liquidity_fraction=args.liquidity_fraction
    )

    engine = StrategyEngine(spec, SingleEntrySignal(entry_ts))
    result = ReplayBacktester(engine, fee_bps=args.fee_bps, max_snapshot_age=max_snapshot_age).run(snapshots, trades)
    summary = summarize_replay(result)

    print(f"Market: {args.coin}")
    print(f"Source: {args.source}")
    print(f"Snapshots: {len(snapshots)}")
    print(f"Trades: {len(trades)}")
    print(f"Book levels: {len(snapshots[0].bids)} bid / {len(snapshots[0].asks)} ask")
    print(f"Desired notional: ${args.notional:,.2f}")
    if args.liquidity_fraction is not None: print(f"Liquidity fraction: {args.liquidity_fraction:.0%}")
    print(f"Entry signal: {utc(entry_ts)}")
    print(f"States evaluated: {result.states_evaluated}")
    print(f"States skipped: {result.states_skipped}")
    print(f"Fills: {len(result.fills)}")
    print(f"Closed trades: {len(result.trades)}")

    print("\nFills:")
    for item in result.fills:
        fill = item.fill
        print(
            f"  {item.action.value}: {fill.side.value} qty={fill.filled_quantity:.8f} "
            f"vwap={fill.average_price:.8f} notional=${fill.filled_notional:.2f} "
            f"slippage={fill.slippage_bps:.4f}bps levels={fill.levels_consumed} full={fill.fully_filled}"
        )

    print("\nTrades:")
    for trade in result.trades:
        print(f"  direction: {trade.direction.value}")
        print(f"  entry: {utc(trade.entry_ts)} @ {trade.entry_price:.8f}")
        print(f"  exit:  {utc(trade.exit_ts)} @ {trade.exit_price:.8f}")
        print(f"  holding: {trade.holding_seconds:.3f}s")
        print(f"  scale-ins: {trade.scale_ins}")
        print(f"  gross PnL: ${trade.gross_pnl:.6f}")
        print(f"  fees: ${trade.fees:.6f}")
        print(f"  net PnL: ${trade.net_pnl:.6f}")

    print("\nPerformance:")
    print(f"  turnover: ${summary.turnover_notional:.2f}")
    print(f"  weighted slippage: {summary.weighted_slippage_bps:.4f}bps")
    print(f"  max drawdown: ${summary.max_drawdown:.6f}")
    print(f"  net PnL: ${summary.net_pnl:.6f}")

    chart_paths = save_backtest_charts(result, 10000, f"data/processed/backtests/{args.coin.lower()}_{args.source}_replay_check")

    print("\nCharts:")
    for path in chart_paths: print(f"  {path}")

if __name__ == "__main__":
    main()