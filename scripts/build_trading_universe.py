import argparse
import json
import time
from pathlib import Path

from hlbot.features.market_movement import latest_realized_volatility
from hlbot.selection.trading_gate import best_tradeable_notional

def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(path)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection",default="data/derived/market_selection/collection_universe.json")
    parser.add_argument("--profile",default="data/derived/market_selection/execution_profile.json")
    parser.add_argument("--universe-dir",default="data/raw/hyperliquid_universe")
    parser.add_argument("--output",default="data/derived/market_selection/trading_universe.json")
    parser.add_argument("--movement-window-minutes", type=float, default=5)
    parser.add_argument("--minimum-full-rate", type=float, default=0.95)
    parser.add_argument("--minimum-movement-cost-ratio", type=float, default=2)
    parser.add_argument("--fee-bps-per-side", type=float, default=5)
    parser.add_argument("--latency-buffer-bps", type=float, default=0)
    parser.add_argument("--max-profile-age-seconds", type=float, default=600)
    parser.add_argument("--trading-rank", type=int, default=10)
    args = parser.parse_args()

    selection = json.loads(Path(args.selection).read_text())
    profile = json.loads(Path(args.profile).read_text())
    now = time.time()
    age = now - profile["checked_ts"]

    if profile["selection_epoch_ts"] != selection["epoch_ts"]:
        raise SystemExit("execution profile belongs to a different selection epoch")

    if age > args.max_profile_age_seconds:
        raise SystemExit(f"execution profile stale: {age:.0f}s > {args.max_profile_age_seconds:.0f}s")

    markets = sorted(profile["markets"], key=lambda row: row["rank"])

    volatility = latest_realized_volatility(
        args.universe_dir,
        [row["coin"] for row in markets],
        now,
        args.movement_window_minutes * 60
    )

    rows = []

    for market in markets:
        coin = market["coin"]
        rv = volatility.get(coin)
        inside_trading_rank = market["rank"] <= args.trading_rank

        row = {
            "dex": market["dex"],
            "coin": coin,
            "rank": market["rank"],
            "inside_trading_rank": inside_trading_rank,
            "execution_supported": market["execution_supported"],
            "l2_ready": market["l2_ready"],
            "realized_volatility_5m": rv,
            "max_tradeable_notional": None,
            "execution_cost_bps": None,
            "movement_cost_ratio": None,
            "tradeable": False
        }

        if (
            inside_trading_rank and
            market["execution_supported"] and
            market["l2_ready"] and
            rv is not None
        ):
            result = best_tradeable_notional(
                market["curve"],
                rv,
                args.minimum_full_rate,
                args.minimum_movement_cost_ratio,
                args.fee_bps_per_side,
                args.latency_buffer_bps
            )

            if result:
                row["max_tradeable_notional"] = result.notional
                row["execution_cost_bps"] = result.cost_bps
                row["movement_cost_ratio"] = result.movement_cost_ratio
                row["tradeable"] = True

        rows.append(row)

    selected = [row for row in rows if row["tradeable"]]

    write(Path(args.output), {
        "checked_ts": now,
        "selection_epoch_ts": profile["selection_epoch_ts"],
        "execution_profile_ts": profile["checked_ts"],
        "execution_profile_age_seconds": age,
        "trading_rank": args.trading_rank,
        "minimum_full_rate": args.minimum_full_rate,
        "minimum_movement_cost_ratio": args.minimum_movement_cost_ratio,
        "fee_bps_per_side": args.fee_bps_per_side,
        "latency_buffer_bps": args.latency_buffer_bps,
        "coins": [row["coin"] for row in selected],
        "markets": rows
    })

    print(
        f"Trading universe: {len(selected)}/{args.trading_rank} "
        f"| profile_age={age:.0f}s"
    )

    for row in rows:
        mark = "*" if row["tradeable"] else " "

        if not row["inside_trading_rank"]:
            status = "reserve"
        elif not row["execution_supported"]:
            status = "unsupported"
        elif not row["l2_ready"]:
            status = "L2 not ready"
        elif row["realized_volatility_5m"] is None:
            status = "no RV5"
        elif not row["tradeable"]:
            status = "cost/movement fail"
        else:
            status = (
                f"size=${row['max_tradeable_notional']:.0f} "
                f"cost={row['execution_cost_bps']:.2f}bps "
                f"ratio={row['movement_cost_ratio']:.2f}"
            )

        print(f"{mark}{row['rank']:2}. {row['coin']:<14} {status}")

if __name__ == "__main__":
    main()