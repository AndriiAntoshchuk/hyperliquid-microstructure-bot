from hlbot.models.order_book import OrderBookSnapshot

def visible_notional(snapshot: OrderBookSnapshot) -> tuple[float, float]:
    bid = sum(level.price * level.quantity for level in snapshot.bids)
    ask = sum(level.price * level.quantity for level in snapshot.asks)
    return bid, ask

def safe_visible_notional(snapshot: OrderBookSnapshot) -> float:
    bid, ask = visible_notional(snapshot)
    return min(bid, ask)

def liquidity_capped_notional(snapshot: OrderBookSnapshot, desired_notional: float, fraction: float = 0.25) -> float:
    if desired_notional <= 0: raise ValueError("desired_notional must be positive")
    if not 0 < fraction <= 1: raise ValueError("fraction must be in (0, 1]")
    return min(desired_notional, safe_visible_notional(snapshot) * fraction)