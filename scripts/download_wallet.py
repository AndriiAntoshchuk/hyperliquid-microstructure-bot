import argparse
from datetime import datetime, timezone

from hlbot.data.wallet_loader import HyperliquidWalletLoader

def parse_date(value: str) -> int:
    dt = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("wallet")
    parser.add_argument("--start", required=True, help="Start date in YYYY-MM-DD format")
    parser.add_argument("--end", help="End date in YYYY-MM-DD format")
    args = parser.parse_args()

    start_time = parse_date(args.start)
    end_time = parse_date(args.end) if args.end else None

    loader = HyperliquidWalletLoader()
    fills, incomplete = loader.download(args.wallet, start_time, end_time)

    print(f"Downloaded fills: {len(fills)}")
    print(f"History may be incomplete: {incomplete}")

if __name__ == "__main__":
    main()