import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import websockets

MAINNET_WS_URL = "wss://api.hyperliquid.xyz/ws"
COLLECTOR_VERSION = "0.2.0"
HEARTBEAT_SECONDS = 30
STATUS_SECONDS = 10
MAX_RECONNECT_SECONDS = 30
CHANNELS = {"l2Book", "bbo", "trades"}

def utc_date_from_ns(timestamp_ns: int) -> str:
    return datetime.fromtimestamp(timestamp_ns / 1_000_000_000, timezone.utc).strftime("%Y-%m-%d")

def output_path(data_dir: str | Path, coin: str, channel: str, timestamp_ns: int) -> Path:
    return Path(data_dir) / f"hyperliquid_ws_{coin}_{channel}_{utc_date_from_ns(timestamp_ns)}.jsonl"

def normalize_coins(coins: str | Iterable[str]) -> tuple[str, ...]:
    if isinstance(coins, str): coins = (coins,)
    result = tuple(dict.fromkeys(coin.strip() for coin in coins if coin.strip()))
    if not result: raise ValueError("at least one coin is required")
    return result

def build_subscriptions(coins: str | Iterable[str], fast_l2: bool = True) -> tuple[dict, ...]:
    subscriptions = []
    for coin in normalize_coins(coins):
        book = {"type": "l2Book", "coin": coin}
        if fast_l2: book["fast"] = True
        subscriptions.extend((book, {"type": "bbo", "coin": coin}, {"type": "trades", "coin": coin}))
    return tuple(subscriptions)

def extract_coin(channel: str, data) -> str | None:
    if channel in {"l2Book", "bbo"} and isinstance(data, dict): return data.get("coin")
    if channel == "trades" and isinstance(data, list) and data: return data[0].get("coin")
    return None

def build_record(channel: str, data, coin: str, connection_id: str, message_index: int, received_ns: int | None = None, fast_l2: bool = False) -> dict:
    received_ns = time.time_ns() if received_ns is None else received_ns
    return {
        "collector_version": COLLECTOR_VERSION,
        "source": "hyperliquid_websocket",
        "coin": coin,
        "channel": channel,
        "fast_l2": fast_l2 if channel == "l2Book" else False,
        "local_receive_ns": received_ns,
        "local_receive_ts": received_ns / 1_000_000_000,
        "connection_id": connection_id,
        "message_index": message_index,
        "data": data
    }

def write_record(data_dir: str | Path, record: dict) -> int:
    path = output_path(data_dir, record["coin"], record["channel"], record["local_receive_ns"])
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, separators=(",", ":")) + "\n"
    with path.open("a") as file:
        file.write(line)
        file.flush()
    return len(line.encode())

def human_bytes(size: int) -> str:
    if size < 1024: return f"{size} B"
    if size < 1024 ** 2: return f"{size / 1024:.1f} KB"
    if size < 1024 ** 3: return f"{size / 1024 ** 2:.1f} MB"
    return f"{size / 1024 ** 3:.2f} GB"

async def heartbeat(websocket) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_SECONDS)
        await websocket.send(json.dumps({"method": "ping"}))

async def status_reporter(stats: dict) -> None:
    while True:
        await asyncio.sleep(STATUS_SECONDS)
        elapsed = time.monotonic() - stats["started"]
        print(
            f"[{elapsed:7.1f}s] books={stats['books']} | bbo={stats['bbo']} | "
            f"trade messages={stats['trade_messages']} | trades={stats['trades']} | "
            f"written={human_bytes(stats['bytes'])}",
            flush=True
        )

async def collect_connection(coins: str | Iterable[str], data_dir: str | Path, url: str = MAINNET_WS_URL, fast_l2: bool = True) -> None:
    coins = normalize_coins(coins)
    connection_id = uuid.uuid4().hex
    message_index = 0
    stats = {"started": time.monotonic(), "books": 0, "bbo": 0, "trade_messages": 0, "trades": 0, "bytes": 0}

    async with websockets.connect(url, ping_interval=None, max_queue=1024) as websocket:
        print(f"Connected to {url}", flush=True)

        for subscription in build_subscriptions(coins, fast_l2):
            await websocket.send(json.dumps({"method": "subscribe", "subscription": subscription}))

        mode = "fast" if fast_l2 else "deep"
        print(f"Subscribed: {', '.join(coins)} | {mode} l2Book + bbo + trades", flush=True)
        print(f"Saving to: {Path(data_dir).resolve()}", flush=True)

        heartbeat_task = asyncio.create_task(heartbeat(websocket))
        status_task = asyncio.create_task(status_reporter(stats))

        try:
            async for raw_message in websocket:
                received_ns = time.time_ns()
                message = json.loads(raw_message)
                channel = message.get("channel")
                if channel not in CHANNELS: continue

                data = message.get("data")
                coin = extract_coin(channel, data)
                if not coin: continue

                message_index += 1
                record = build_record(channel, data, coin, connection_id, message_index, received_ns, fast_l2)
                stats["bytes"] += write_record(data_dir, record)

                if channel == "l2Book": stats["books"] += 1
                elif channel == "bbo": stats["bbo"] += 1
                elif channel == "trades":
                    stats["trade_messages"] += 1
                    if isinstance(data, list): stats["trades"] += len(data)
        finally:
            heartbeat_task.cancel()
            status_task.cancel()
            for task in (heartbeat_task, status_task):
                try: await task
                except asyncio.CancelledError: pass

async def run_collector(coins: str | Iterable[str], data_dir: str | Path, url: str = MAINNET_WS_URL, fast_l2: bool = True) -> None:
    delay = 1
    while True:
        try:
            print(f"Connecting to Hyperliquid WebSocket for {', '.join(normalize_coins(coins))}...", flush=True)
            await collect_connection(coins, data_dir, url, fast_l2)
            delay = 1
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"WebSocket error: {error}", flush=True)
            print(f"Reconnecting in {delay}s...", flush=True)
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_RECONNECT_SECONDS)