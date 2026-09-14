import argparse
import asyncio

from hlbot.data.hyperliquid_ws_collector import run_collector

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--coin", default="PONS")
    parser.add_argument("--data-dir", default="data/raw/hyperliquid_ws")
    args = parser.parse_args()

    asyncio.run(run_collector(args.coin, args.data_dir))

if __name__ == "__main__":
    main()