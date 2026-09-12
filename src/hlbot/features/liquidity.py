from hlbot.models.order_book import OrderBookSnapshot

def liquidity_within_bps(snapshot: OrderBookSnapshot, bps: float) -> tuple[float, float]:
    if bps <= 0: raise ValueError("bps must be positive")

    mid = snapshot.mid_price
    lower = mid * (1 - bps / 10_000)
    upper = mid * (1 + bps / 10_000)

    bid_liquidity = sum(level.quantity for level in snapshot.bids if level.price >= lower)
    ask_liquidity = sum(level.quantity for level in snapshot.asks if level.price <= upper)

    return bid_liquidity, ask_liquidity