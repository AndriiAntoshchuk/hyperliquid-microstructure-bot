import argparse

from hlbot.data.universe_collector import UniverseCollector

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=float, default=60)
    parser.add_argument("--output", default="data/raw/hyperliquid_universe")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    collector = UniverseCollector(args.output, args.interval)

    if args.once:
        rows = collector.collect_once()
        print(f"markets={len(rows)} active={sum(row.active for row in rows)}")
        return

    collector.run()

if __name__ == "__main__":
    main()