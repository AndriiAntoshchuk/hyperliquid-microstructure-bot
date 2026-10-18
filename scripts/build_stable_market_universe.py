import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from hlbot.data.universe_collector import UniverseMarket
from hlbot.selection.engine import MarketSelectionEngine
from hlbot.selection.market_selector import MarketSelectorConfig
from hlbot.selection.stable_selector import (
    StableSelectionConfig,
    aggregate_market_selection,
    build_stable_selection_plan,
    collection_since_map,
)


def snapshots(directory):
    ts, rows = None, []

    for path in sorted(directory.glob("universe_*.jsonl")):
        for line in path.open():
            row = UniverseMarket(**json.loads(line))

            if ts is not None and row.ts != ts:
                yield tuple(rows)
                rows = []

            ts = row.ts
            rows.append(row)

    if rows: yield tuple(rows)

def rankings(raw, start, end):
    engine = MarketSelectionEngine(MarketSelectorConfig(top_n=10_000))
    result = []

    for snapshot in raw:
        ts = snapshot[0].ts
        if ts < start - 3600: continue
        if ts > end: break

        selection = engine.update(snapshot)
        if ts > start: result.append(selection)

    return tuple(result)

def load_state(path):
    if not path.exists(): return {}, None

    data = json.loads(path.read_text())
    return {(row["dex"], row["coin"]): row["collection_since"] for row in data.get("collection", [])}, data.get("epoch_ts")

def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(path)

def iso(ts):
    return datetime.fromtimestamp(ts, UTC).isoformat()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/raw/hyperliquid_universe")
    parser.add_argument("--output-dir", default="data/derived/market_selection")
    parser.add_argument("--window-hours", type=float, default=6)
    parser.add_argument("--epoch-hours", type=float, default=6)
    parser.add_argument("--entry-rank", type=int, default=20)
    parser.add_argument("--retention-rank", type=int, default=30)
    parser.add_argument("--trading-rank", type=int, default=10)
    parser.add_argument("--warmup-minutes", type=float, default=60)
    args = parser.parse_args()

    raw = tuple(snapshots(Path(args.input)))
    if not raw: raise SystemExit("no universe snapshots found")

    epoch_seconds = args.epoch_hours * 3600
    latest = raw[-1][0].ts
    epoch = latest - latest % epoch_seconds

    config = StableSelectionConfig(
        window_seconds=args.window_hours * 3600,
        epoch_seconds=epoch_seconds,
        entry_rank=args.entry_rank,
        retention_rank=args.retention_rank,
        trading_rank=args.trading_rank,
        min_collection_age_seconds=args.warmup_minutes * 60
    )

    start = epoch - config.window_seconds
    selections = rankings(raw, start, epoch)
    if not selections: raise SystemExit("no snapshots in completed selection window")

    markets = aggregate_market_selection(selections, config)
    output = Path(args.output_dir)
    state = output / "stable_selection_state.json"
    previous, previous_epoch = load_state(state)

    if previous_epoch is not None and previous_epoch > epoch:
        raise SystemExit("selection state is newer than current epoch")

    plan = build_stable_selection_plan(markets, epoch, previous, config)

    write(output / "stable_ranking.json", {
        "epoch_ts": epoch,
        "epoch_utc": iso(epoch),
        "window_start_ts": start,
        "window_start_utc": iso(start),
        "window_snapshots": len(selections),
        "markets": [asdict(row) for row in markets]
    })

    write(output / "collection_universe.json", {
        "epoch_ts": epoch,
        "epoch_utc": iso(epoch),
        "coins": [row.coin for row in plan.collection],
        "markets": [asdict(row) for row in plan.collection]
    })

    write(output / "trading_universe.json", {
        "epoch_ts": epoch,
        "epoch_utc": iso(epoch),
        "requires_l2_validation": True,
        "coins": [row.coin for row in plan.trading_candidates],
        "markets": [asdict(row) for row in plan.trading_candidates]
    })

    write(state, {
        "epoch_ts": epoch,
        "epoch_utc": iso(epoch),
        "collection": [
            {"dex": dex, "coin": coin, "collection_since": since}
            for (dex, coin), since in collection_since_map(plan).items()
        ]
    })

    print(f"epoch={iso(epoch)} window={iso(start)} -> {iso(epoch)} snapshots={len(selections)}")
    print("\nCollection universe:")

    for row in plan.collection:
        age = (epoch - row.collection_since) / 60
        print(
            f"{row.rank:2}. {row.coin:<18} "
            f"score={row.aggregate_score:.3f} "
            f"persist={row.persistence:.1%} age={age:.0f}m"
        )

    print("\nTrading candidates:")
    if not plan.trading_candidates:
        print("none — warm-up required")
    else:
        for row in plan.trading_candidates:
            print(f"{row.rank:2}. {row.coin:<18} score={row.aggregate_score:.3f}")

if __name__ == "__main__":
    main()