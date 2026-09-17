from statistics import median

from hlbot.data.hyperliquid_ws_loader import load_ws_market_data

COINS = ("PONS", "CASHCAT", "PURR", "LIT")
NOTIONALS = (100, 250, 500, 1000)

FRACTIONS = (.10, .25, .50)


def capacity(levels) -> float:
    return sum(level.price * level.quantity for level in levels)

def percentile(values: list[float], p: float) -> float:
    values = sorted(values)
    return values[int((len(values) - 1) * p)]

def summarize(values: list[float]) -> str:
    return (
        f"min=${min(values):8.2f} "
        f"p10=${percentile(values, .10):8.2f} "
        f"p50=${median(values):8.2f} "
        f"p90=${percentile(values, .90):8.2f} "
        f"max=${max(values):8.2f}"
    )

def coverage(values: list[float], notional: float) -> float:
    return sum(value >= notional for value in values) / len(values) * 100

def main():
    for coin in COINS:
        books, _ = load_ws_market_data("data/raw/hyperliquid_ws_fast", coin)
        buy_capacity = [capacity(book.asks) for book in books]
        sell_capacity = [capacity(book.bids) for book in books]
        safe = [safe_capacity(book) for book in books]

        print(f"\n{coin} snapshots={len(books)}")
        print(f"buy  {summarize(buy_capacity)}")
        print(f"sell {summarize(sell_capacity)}")
        print(f"safe {summarize(safe)}")

        for notional in NOTIONALS:
            print(
                f"${notional:4} full-depth coverage: "
                f"buy={coverage(buy_capacity, notional):6.2f}% "
                f"sell={coverage(sell_capacity, notional):6.2f}%"
            )

        for fraction in FRACTIONS:
            sizes = [value * fraction for value in safe]
            print(
                f"{fraction:>4.0%} safe size: "
                f"p10=${percentile(sizes, .10):8.2f} "
                f"p50=${median(sizes):8.2f} "
                f"p90=${percentile(sizes, .90):8.2f}"
            )

def safe_capacity(book) -> float:
    return min(capacity(book.bids), capacity(book.asks))

if __name__ == "__main__":
    main()