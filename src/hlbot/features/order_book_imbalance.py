from hlbot.models.order_book import OrderBookSnapshot

def order_book_imbalance(snapshot: OrderBookSnapshot, depth: int = 1) -> float:
    if depth <= 0: raise ValueError("depth must be positive")

    bid_volume = sum(level.quantity for level in snapshot.bids[:depth])
    ask_volume = sum(level.quantity for level in snapshot.asks[:depth])
    total = bid_volume + ask_volume

    return 0.0 if total == 0 else (bid_volume - ask_volume) / total

def weighted_order_book_imbalance(snapshot: OrderBookSnapshot, depth: int = 5) -> float:
    if depth <= 0: raise ValueError("depth must be positive")

    bid_volume = sum(level.quantity / (index + 1) for index, level in enumerate(snapshot.bids[:depth]))
    ask_volume = sum(level.quantity / (index + 1) for index, level in enumerate(snapshot.asks[:depth]))
    total = bid_volume + ask_volume

    return 0.0 if total == 0 else (bid_volume - ask_volume) / total