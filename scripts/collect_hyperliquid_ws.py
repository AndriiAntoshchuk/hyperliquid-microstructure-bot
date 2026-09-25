import argparse
import asyncio

from hlbot.data.hyperliquid_ws_collector import run_collector

DEFAULT_COINS = ("PONS", "CASHCAT", "PURR", "LIT")
DEFAULT_UNIVERSE = "data/derived/market_selection/collection_universe.json"

async def run(args):
    coins = args.coins or ([args.coin] if args.coin else DEFAULT_COINS)
    universe_file = args.universe_file if args.dynamic else None

    task = asyncio.create_task(
        run_collector(
            coins,
            args.data_dir,
            fast_l2=not args.deep_l2,
            universe_file=universe_file,
            refresh_seconds=args.refresh_seconds
        )
    )

    if args.duration is None:
        await task
        return

    try:
        await asyncio.sleep(args.duration)
    finally:
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--coin")
    parser.add_argument("--coins", nargs="+")
    parser.add_argument("--data-dir", default="data/raw/hyperliquid_ws_fast")
    parser.add_argument("--duration", type=float)
    parser.add_argument("--deep-l2", action="store_true")
    parser.add_argument("--dynamic", action="store_true")
    parser.add_argument("--universe-file", default=DEFAULT_UNIVERSE)
    parser.add_argument("--refresh-seconds", type=float, default=30)
    args = parser.parse_args()
    asyncio.run(run(args))

if __name__ == "__main__":
    main()