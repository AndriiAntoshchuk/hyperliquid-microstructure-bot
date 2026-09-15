import json
from pathlib import Path
from typing import Iterator

from hlbot.models.order_book import OrderBookLevel, OrderBookSnapshot
from hlbot.models.trade import Trade, TradeSide

def _iter_json_objects(path: str | Path, chunk_size: int = 1024 * 1024) -> Iterator[dict]:
    decoder = json.JSONDecoder()
    buffer = ""

    with open(path) as file:
        while True:
            chunk = file.read(chunk_size)
            if chunk: buffer += chunk

            index = 0

            while True:
                while index < len(buffer) and buffer[index].isspace(): index += 1

                if index >= len(buffer):
                    buffer = ""
                    break

                try:
                    row, end = decoder.raw_decode(buffer, index)
                except json.JSONDecodeError:
                    buffer = buffer[index:]
                    break

                if not isinstance(row, dict): raise ValueError(f"Expected JSON object in {path}")

                yield row
                index = end

            if not chunk:
                if buffer.strip(): raise ValueError(f"Incomplete or malformed JSON in {path}")
                break

def load_trades(path: str | Path) -> list[Trade]:
    trades = []

    for row in _iter_json_objects(path):
        if "exchange_ts" not in row or "local_ts" not in row: continue

        trades.append(
            Trade(
                trade_id=str(row["trade_id"]),
                exchange=str(row["exchange"]),
                trading_pair=str(row["trading_pair"]),
                exchange_ts=float(row["exchange_ts"]),
                local_ts=float(row["local_ts"]),
                price=float(row["price"]),
                quantity=float(row["q_base"]),
                side=TradeSide(row["side"])
            )
        )

    return trades

def load_order_books(path: str | Path) -> list[OrderBookSnapshot]:
    snapshots = []

    for row in _iter_json_objects(path):
        if "exchange_ts" not in row or "local_ts" not in row or "update_id" not in row: continue

        snapshots.append(
            OrderBookSnapshot(
                exchange=str(row["exchange"]),
                trading_pair=str(row["trading_pair"]),
                exchange_ts=float(row["exchange_ts"]),
                local_ts=float(row["local_ts"]),
                update_id=int(row["update_id"]),
                bids=tuple(OrderBookLevel(float(price), float(quantity)) for price, quantity in row["bids"]),
                asks=tuple(OrderBookLevel(float(price), float(quantity)) for price, quantity in row["asks"])
            )
        )

    return snapshots

def load_market_data_directory(data_dir: str | Path, trading_pair: str) -> tuple[list[OrderBookSnapshot], list[Trade]]:
    directory = Path(data_dir)

    book_files = sorted(directory.glob(
        f"hyperliquid_perpetual_{trading_pair}_order_book_snapshots_*.txt"
    ))

    trade_files = sorted(directory.glob(
        f"hyperliquid_perpetual_{trading_pair}_trades_*.txt"
    ))

    snapshots = []
    trades = []

    for path in book_files:
        snapshots.extend(load_order_books(path))

    for path in trade_files:
        trades.extend(load_trades(path))

    unique_snapshots = {}
    unique_trades = {}

    for snapshot in snapshots:
        key = (snapshot.exchange, snapshot.trading_pair, snapshot.update_id)
        unique_snapshots[key] = snapshot

    for trade in trades:
        unique_trades[trade.trade_id] = trade

    snapshots = sorted(
        unique_snapshots.values(),
        key=lambda snapshot: (snapshot.exchange_ts, snapshot.local_ts)
    )

    trades = sorted(
        unique_trades.values(),
        key=lambda trade: (trade.exchange_ts, trade.local_ts)
    )

    return snapshots, trades