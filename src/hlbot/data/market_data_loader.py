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