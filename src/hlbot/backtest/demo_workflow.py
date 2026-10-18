import json
import re
from dataclasses import asdict
from pathlib import Path

from hlbot.backtest.performance import summarize_replay
from hlbot.backtest.replay import ReplayBacktester
from hlbot.data.hyperliquid_ws_loader import load_ws_market_data
from hlbot.strategy.demo_signal import DemoMeanReversionSignal
from hlbot.strategy.engine import StrategyEngine
from hlbot.strategy.specification import StrategySpec


def run_backtest(config_path: str | Path, data_dir: str | Path, output_path: str | Path) -> dict:
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if config.get("signal") != "demo_mean_reversion":
        raise ValueError("only the illustrative demo_mean_reversion signal is supported")

    coin = config["coin"]
    if not isinstance(coin, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", coin):
        raise ValueError("coin must be an alphanumeric market symbol")

    snapshots, trades = load_ws_market_data(data_dir, coin)
    if not snapshots:
        raise ValueError(f"no {coin} l2Book snapshots found under {data_dir}")

    strategy = StrategySpec(**config["strategy"])
    signal = DemoMeanReversionSignal(**config.get("signal_parameters", {}))
    engine = StrategyEngine(strategy, signal)
    backtester = ReplayBacktester(
        engine,
        max_snapshot_age=float(config.get("max_snapshot_age", 2.0)),
        fee_bps=float(config.get("fee_bps", 4.5)),
    )
    result = backtester.run(snapshots, trades)
    performance = summarize_replay(result)

    report = {
        "kind": "illustrative_historical_replay_not_investment_results",
        "market": coin,
        "config": config,
        "input": {"snapshots": len(snapshots), "trades": len(trades)},
        "replay": {"states_evaluated": result.states_evaluated, "states_skipped": result.states_skipped,
                   "has_open_position": result.final_position is not None},
        "performance": asdict(performance),
        "trades": [
            {**asdict(trade), "direction": trade.direction.value,
             "holding_seconds": trade.holding_seconds}
            for trade in result.trades
        ],
        "fills": [
            {"action": item.action.value, "execution_mode": item.execution_mode.value,
             "fee_paid": item.fee_paid, "side": item.fill.side.value,
             "quantity": item.fill.filled_quantity,
             "price": item.fill.average_price,
             "notional": item.fill.filled_notional,
             "timestamp": item.fill.timestamp}
            for item in result.fills
        ],
    }
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report
