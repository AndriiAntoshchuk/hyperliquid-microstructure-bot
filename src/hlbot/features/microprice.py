from hlbot.models.order_book import OrderBookSnapshot

def microprice(snapshot: OrderBookSnapshot) -> float:
    bid = snapshot.bids[0]
    ask = snapshot.asks[0]
    total_quantity = bid.quantity + ask.quantity

    if total_quantity == 0: return (bid.price + ask.price) / 2
    return (ask.price * bid.quantity + bid.price * ask.quantity) / total_quantity