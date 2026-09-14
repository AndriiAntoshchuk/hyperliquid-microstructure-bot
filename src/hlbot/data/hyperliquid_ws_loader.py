import json
from pathlib import Path

from hlbot.models.order_book import OrderBookLevel, OrderBookSnapshot
from hlbot.models.trade import Trade, TradeSide

EXCHANGE = "hyperliquid_perpetual"

def _load_records(path: str | Path):
    path = Path(path)

    with path.open() as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip(): continue

            try:
                yield json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON in {path} at line {line_number}") from error

def _local_ts(record: dict) -> float:
    if "local_receive_ts" in record: return float(record["local_receive_ts"])
    return int(record["local_receive_ns"]) / 1_000_000_000

def _trading_pair(coin: str) -> str:
    return f"{coin}-USD"

def load_ws_order_books(path: str | Path) -> list[OrderBookSnapshot]:
    snapshots = []

    for record in _load_records(path):
        if record.get("channel") != "l2Book": continue

        data = record.get("data")

        if not isinstance(data, dict): raise ValueError("l2Book data must be an object")

        levels = data.get("levels")

        if not isinstance(levels, list) or len(levels) != 2:
            raise ValueError("l2Book levels must contain bids and asks")

        coin = str(data.get("coin", record.get("coin", "")))

        if not coin: raise ValueError("l2Book record has no coin")

        bids = tuple(
            OrderBookLevel(
                price=float(level["px"]),
                quantity=float(level["sz"])
            )
            for level in levels[0]
        )

        asks = tuple(
            OrderBookLevel(
                price=float(level["px"]),
                quantity=float(level["sz"])
            )
            for level in levels[1]
        )

        snapshots.append(
            OrderBookSnapshot(
                exchange=EXCHANGE,
                trading_pair=_trading_pair(coin),
                exchange_ts=float(data["time"]) / 1000,
                local_ts=_local_ts(record),
                update_id=int(record["local_receive_ns"]),
                bids=bids,
                asks=asks
            )
        )

    return snapshots

def load_ws_trades(path: str | Path) -> list[Trade]:
    trades = []
    seen = set()

    for record in _load_records(path):
        if record.get("channel") != "trades": continue

        data = record.get("data")

        if not isinstance(data, list): raise ValueError("trades data must be a list")

        local_ts = _local_ts(record)

        for item in data:
            coin = str(item.get("coin", record.get("coin", "")))

            if not coin: raise ValueError("trade record has no coin")

            side = item["side"]

            if side == "B":
                trade_side = TradeSide.BUY
            elif side == "A":
                trade_side = TradeSide.SELL
            else:
                raise ValueError(f"Unknown Hyperliquid trade side: {side}")

            timestamp_ms = int(item["time"])
            trade_id = f"{timestamp_ms}:{coin}:{item['tid']}"

            if trade_id in seen: continue
            seen.add(trade_id)

            trades.append(
                Trade(
                    trade_id=trade_id,
                    exchange=EXCHANGE,
                    trading_pair=_trading_pair(coin),
                    exchange_ts=timestamp_ms / 1000,
                    local_ts=local_ts,
                    price=float(item["px"]),
                    quantity=float(item["sz"]),
                    side=trade_side
                )
            )

    return sorted(trades, key=lambda trade: trade.exchange_ts)

def load_ws_market_data(data_dir: str | Path, coin: str) -> tuple[list[OrderBookSnapshot], list[Trade]]:
    directory = Path(data_dir)

    book_paths = sorted(directory.glob(f"hyperliquid_ws_{coin}_l2Book_*.jsonl"))
    trade_paths = sorted(directory.glob(f"hyperliquid_ws_{coin}_trades_*.jsonl"))

    snapshots = []
    trades = []

    for path in book_paths:
        snapshots.extend(load_ws_order_books(path))

    for path in trade_paths:
        trades.extend(load_ws_trades(path))

    snapshots.sort(key=lambda snapshot: (snapshot.exchange_ts, snapshot.local_ts))

    seen = set()
    unique_trades = []

    for trade in sorted(trades, key=lambda item: item.exchange_ts):
        if trade.trade_id in seen: continue
        seen.add(trade.trade_id)
        unique_trades.append(trade)

    return snapshots, unique_trades