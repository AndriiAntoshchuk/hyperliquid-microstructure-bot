import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

from hlbot.data.universe_collector import UniverseMarket
from hlbot.selection.engine import MarketSelectionEngine, MarketSelectionSnapshot
from hlbot.selection.market_selector import MarketSelectorConfig

def snapshots(lines):
    ts = None
    rows = []

    for line in lines:
        row = UniverseMarket(**json.loads(line))
        if ts is not None and row.ts != ts:
            yield tuple(rows)
            rows = []
        ts = row.ts
        rows.append(row)

    if rows: yield tuple(rows)

def replay(paths, engine):
    latest = None

    for path in paths:
        with path.open() as file:
            for snapshot in snapshots(file):
                latest = engine.update(snapshot)

    return latest

def emit(result: MarketSelectionSnapshot, output: Path) -> None:
    markets = {(row.dex, row.coin): row for row in result.markets}
    candidates = []

    for candidate in result.candidates:
        market = markets[candidate.dex, candidate.coin]
        row = asdict(candidate)
        row.update({
            "day_notional_volume": market.day_notional_volume,
            "volume_5m": market.volume_5m,
            "realized_volatility_5m": market.realized_volatility_5m,
            "realized_volatility_15m": market.realized_volatility_15m
        })
        candidates.append(row)

    payload = {
        "ts": result.ts,
        "coins": result.coins,
        "candidates": candidates
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, separators=(",", ":")))
    tmp.replace(output)

def print_selection(result: MarketSelectionSnapshot) -> None:
    markets = {(row.dex, row.coin): row for row in result.markets}
    print(f"\n{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(result.ts))}")

    for i, candidate in enumerate(result.candidates, 1):
        market = markets[candidate.dex, candidate.coin]
        print(
            f"{i:2}. {candidate.coin:<18} "
            f"score={candidate.score:.3f} "
            f"rv5={_pct(market.realized_volatility_5m)} "
            f"rv15={_pct(market.realized_volatility_15m)} "
            f"vol24h=${market.day_notional_volume / 1_000_000:.1f}M "
            f"warm={candidate.warm}"
        )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/raw/hyperliquid_universe")
    parser.add_argument("--output", default="data/derived/market_selection/latest.json")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--history-files", type=int, default=2)
    parser.add_argument("--poll", type=float, default=2)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    directory = Path(args.input)
    paths = sorted(directory.glob("universe_*.jsonl"))[-args.history_files:]
    if not paths: raise SystemExit("no universe files found")

    engine = MarketSelectionEngine(MarketSelectorConfig(top_n=args.top_n))
    result = replay(paths, engine)
    if result is None: raise SystemExit("no universe snapshots found")

    emit(result, Path(args.output))
    print_selection(result)
    if args.once: return

    current = paths[-1]
    offset = current.stat().st_size
    previous_coins = result.coins

    while True:
        time.sleep(args.poll)
        paths = sorted(directory.glob("universe_*.jsonl"))
        if not paths: continue

        latest = paths[-1]
        if latest != current:
            current = latest
            offset = 0

        if time.time() - current.stat().st_mtime < 1: continue

        with current.open() as file:
            file.seek(offset)
            lines = file.readlines()
            offset = file.tell()

        for snapshot in snapshots(lines):
            result = engine.update(snapshot)
            emit(result, Path(args.output))

            if result.coins != previous_coins:
                print_selection(result)
                previous_coins = result.coins

def _pct(value):
    return "-" if value is None else f"{value:.3%}"

if __name__ == "__main__":
    main()