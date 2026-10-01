from hlbot.models.order_book import OrderBookSnapshot

def liquidity_within_bps(snapshot: OrderBookSnapshot, bps: float) -> tuple[float, float]:
    if bps <= 0: raise ValueError("bps must be positive")
    mid = snapshot.mid_price
    lower = mid * (1 - bps / 10_000)
    upper = mid * (1 + bps / 10_000)
    bid_liquidity = sum(level.quantity for level in snapshot.bids if level.price >= lower)
    ask_liquidity = sum(level.quantity for level in snapshot.asks if level.price <= upper)
    return bid_liquidity, ask_liquidity

def liquidity_notional_within_bps(snapshot: OrderBookSnapshot, bps: float) -> tuple[float, float]:
    if bps <= 0: raise ValueError("bps must be positive")
    mid = snapshot.mid_price
    lower = mid * (1 - bps / 10_000)
    upper = mid * (1 + bps / 10_000)
    bid_liquidity = sum(level.price * level.quantity for level in snapshot.bids if level.price >= lower)
    ask_liquidity = sum(level.price * level.quantity for level in snapshot.asks if level.price <= upper)
    return bid_liquidity, ask_liquidity

def book_depth_notional(snapshot: OrderBookSnapshot, depth: int | None = None) -> tuple[float, float]:
    if depth is not None and depth <= 0: raise ValueError("depth must be positive")
    bids = snapshot.bids if depth is None else snapshot.bids[:depth]
    asks = snapshot.asks if depth is None else snapshot.asks[:depth]
    return (
        sum(level.price * level.quantity for level in bids),
        sum(level.price * level.quantity for level in asks)
    )