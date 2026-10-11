from math import isfinite
from hlbot.models.order_book import OrderBookSnapshot

def visible_notional(snapshot: OrderBookSnapshot) -> tuple[float, float]:
    bid = sum(level.price * level.quantity for level in snapshot.bids)
    ask = sum(level.price * level.quantity for level in snapshot.asks)
    return bid, ask

def safe_visible_notional(snapshot: OrderBookSnapshot) -> float:
    bid, ask = visible_notional(snapshot)
    return min(bid, ask)

def cap_notional(desired_notional: float, bid_notional: float, ask_notional: float, fraction: float = 0.25) -> float:
    if not isfinite(desired_notional) or desired_notional <= 0:
        raise ValueError("desired_notional must be positive and finite")

    if not isfinite(bid_notional) or bid_notional < 0:
        raise ValueError("bid_notional must be non-negative and finite")

    if not isfinite(ask_notional) or ask_notional < 0:
        raise ValueError("ask_notional must be non-negative and finite")

    if not isfinite(fraction) or not 0 < fraction <= 1:
        raise ValueError("fraction must be in (0, 1]")

    return min(desired_notional, min(bid_notional, ask_notional) * fraction)

def liquidity_capped_notional(snapshot: OrderBookSnapshot, desired_notional: float, fraction: float = 0.25) -> float:
    bid, ask = visible_notional(snapshot)
    return cap_notional(desired_notional, bid, ask, fraction)