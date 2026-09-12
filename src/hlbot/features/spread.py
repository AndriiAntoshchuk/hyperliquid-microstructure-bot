from hlbot.models.order_book import OrderBookSnapshot

def mid_price(snapshot: OrderBookSnapshot) -> float:
    return (snapshot.best_bid + snapshot.best_ask) / 2

def spread(snapshot: OrderBookSnapshot) -> float:
    return snapshot.best_ask - snapshot.best_bid

def spread_bps(snapshot: OrderBookSnapshot) -> float:
    mid = mid_price(snapshot)
    return spread(snapshot) / mid * 10_000