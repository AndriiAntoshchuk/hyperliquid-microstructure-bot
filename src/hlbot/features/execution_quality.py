import json
from dataclasses import dataclass
from pathlib import Path

from hlbot.data.l2_coverage import reverse_lines

@dataclass(frozen=True)
class ExecutionQuality:
    coin: str
    snapshots: int
    buy_full_rate: float
    sell_full_rate: float
    spread_p50_bps: float
    spread_p90_bps: float
    buy_slippage_p50_bps: float | None
    buy_slippage_p90_bps: float | None
    sell_slippage_p50_bps: float | None
    sell_slippage_p90_bps: float | None
    round_trip_p90_bps: float | None
    two_sided_depth_p10: float
    two_sided_depth_p50: float

def percentile(values, q):
    if not values: return None
    values = sorted(values)
    pos = (len(values) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(values) - 1)
    weight = pos - lo
    return values[lo] * (1 - weight) + values[hi] * weight

def recent_books(data_dir: str | Path, coin: str, cutoff: float):
    result = []
    pattern = f"hyperliquid_ws_{coin}_l2Book_*.jsonl"

    for path in reversed(sorted(Path(data_dir).glob(pattern))):
        for line in reverse_lines(path):
            try:
                record = json.loads(line)
                ts = float(record["local_receive_ts"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue

            if ts < cutoff: return tuple(result)
            result.append(record)

    return tuple(result)

def parse_levels(record):
    try:
        bids, asks = record["data"]["levels"]
        bids = tuple((float(row["px"]), float(row["sz"])) for row in bids)
        asks = tuple((float(row["px"]), float(row["sz"])) for row in asks)
    except (KeyError, TypeError, ValueError):
        return None

    if not bids or not asks or bids[0][0] >= asks[0][0]: return None
    return bids, asks

def walk_book(levels, notional):
    remaining = notional
    base = 0.0

    for price, size in levels:
        quote = price * size
        used = min(remaining, quote)
        base += used / price
        remaining -= used
        if remaining <= 1e-9: break

    if remaining > 1e-9: return None
    return notional / base

def walk_book_many(levels, notionals):
    targets = sorted(set(float(x) for x in notionals))
    result = {target: None for target in targets}
    quote = base = 0.0
    index = 0

    for price, size in levels:
        level_quote = price * size

        while index < len(targets) and targets[index] <= quote + level_quote + 1e-9:
            target = targets[index]
            target_base = base + (target - quote) / price
            result[target] = target / target_base
            index += 1

        quote += level_quote
        base += size
        if index == len(targets): break

    return result

def analyze_execution_curve(
    data_dir: str | Path,
    coin: str,
    now: float,
    notionals,
    window_seconds: float = 3600
):
    notionals = tuple(dict.fromkeys(float(x) for x in notionals))
    if not notionals or any(x <= 0 for x in notionals):
        raise ValueError("notionals must be positive")

    books = recent_books(data_dir, coin, now - window_seconds)
    spreads, depths = [], []
    buy_slip = {x: [] for x in notionals}
    sell_slip = {x: [] for x in notionals}
    buy_full = {x: 0 for x in notionals}
    sell_full = {x: 0 for x in notionals}
    valid = 0

    for record in books:
        levels = parse_levels(record)
        if not levels: continue

        bids, asks = levels
        bid, ask = bids[0][0], asks[0][0]
        mid = (bid + ask) / 2
        valid += 1

        spreads.append((ask - bid) / mid * 10_000)
        depths.append(min(
            sum(px * sz for px, sz in bids),
            sum(px * sz for px, sz in asks)
        ))

        buys = walk_book_many(asks, notionals)
        sells = walk_book_many(bids, notionals)

        for notional in notionals:
            if buys[notional] is not None:
                buy_full[notional] += 1
                buy_slip[notional].append(
                    (buys[notional] / ask - 1) * 10_000
                )

            if sells[notional] is not None:
                sell_full[notional] += 1
                sell_slip[notional].append(
                    (1 - sells[notional] / bid) * 10_000
                )

    spread50 = percentile(spreads, 0.5) or 0
    spread90 = percentile(spreads, 0.9) or 0
    depth10 = percentile(depths, 0.1) or 0
    depth50 = percentile(depths, 0.5) or 0
    result = []

    for notional in notionals:
        buy90 = percentile(buy_slip[notional], 0.9)
        sell90 = percentile(sell_slip[notional], 0.9)

        result.append((
            notional,
            ExecutionQuality(
                coin=coin,
                snapshots=valid,
                buy_full_rate=buy_full[notional] / valid if valid else 0,
                sell_full_rate=sell_full[notional] / valid if valid else 0,
                spread_p50_bps=spread50,
                spread_p90_bps=spread90,
                buy_slippage_p50_bps=percentile(buy_slip[notional], 0.5),
                buy_slippage_p90_bps=buy90,
                sell_slippage_p50_bps=percentile(sell_slip[notional], 0.5),
                sell_slippage_p90_bps=sell90,
                round_trip_p90_bps=(
                    None if buy90 is None or sell90 is None
                    else buy90 + sell90
                ),
                two_sided_depth_p10=depth10,
                two_sided_depth_p50=depth50
            )
        ))

    return tuple(result)

def analyze_execution_quality(
    data_dir: str | Path,
    coin: str,
    now: float,
    notional: float = 1000,
    window_seconds: float = 3600
):
    return analyze_execution_curve(
        data_dir,
        coin,
        now,
        (notional,),
        window_seconds
    )[0][1]