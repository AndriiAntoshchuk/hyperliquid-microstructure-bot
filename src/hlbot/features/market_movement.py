import json
import math
from pathlib import Path

from hlbot.data.l2_coverage import reverse_lines

def realized_volatility(prices):
    prices = tuple(prices)
    if len(prices) < 2: return None

    returns = [
        math.log(current / previous)
        for previous, current in zip(prices, prices[1:])
        if previous > 0 and current > 0
    ]

    if not returns: return None
    return math.sqrt(sum(value * value for value in returns))

def latest_realized_volatility(
    data_dir: str | Path,
    coins,
    now: float,
    window_seconds: float = 300
):
    coins = set(coins)
    cutoff = now - window_seconds
    points = {coin: [] for coin in coins}
    anchored = set()

    for path in reversed(sorted(Path(data_dir).glob("universe_*.jsonl"))):
        for line in reverse_lines(path):
            try:
                row = json.loads(line)
                coin = row["coin"]
                ts = float(row["ts"])
                price = row.get("mid_price")
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue

            if coin not in coins or price is None: continue

            if ts >= cutoff:
                points[coin].append((ts, float(price)))

            elif coin not in anchored:
                points[coin].append((ts, float(price)))
                anchored.add(coin)

            if ts < cutoff - 120 and anchored == coins:
                break

        if anchored == coins:
            break

    result = {}

    for coin, rows in points.items():
        rows.sort()
        result[coin] = realized_volatility(
            price for _, price in rows
        )

    return result