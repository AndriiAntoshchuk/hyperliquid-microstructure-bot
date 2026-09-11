from dataclasses import dataclass

@dataclass(frozen=True)
class OrderBookLevel:
    price: float
    quantity: float

    def __post_init__(self):
        if self.price <= 0:
            raise ValueError("price must be positive")

        if self.quantity <= 0:
            raise ValueError("quantity must be positive")

@dataclass(frozen=True)
class OrderBookSnapshot:
    exchange: str
    trading_pair: str
    exchange_ts: float
    local_ts: float
    update_id: int
    bids: tuple[OrderBookLevel, ...]
    asks: tuple[OrderBookLevel, ...]

    def __post_init__(self):
        if not self.exchange: raise ValueError("exchange cannot be empty")

        if not self.trading_pair: raise ValueError("trading_pair cannot be empty")

        if self.exchange_ts <= 0: raise ValueError("exchange_ts must be positive")

        if self.local_ts <= 0: raise ValueError("local_ts must be positive")

        if self.update_id <= 0: raise ValueError("update_id must be positive")

        if not self.bids: raise ValueError("bids cannot be empty")

        if not self.asks: raise ValueError("asks cannot be empty")

        bid_prices = [level.price for level in self.bids]
        ask_prices = [level.price for level in self.asks]

        if bid_prices != sorted(bid_prices, reverse=True): raise ValueError("bids must be sorted highest to lowest")

        if ask_prices != sorted(ask_prices): raise ValueError("asks must be sorted lowest to highest")

        if self.best_bid >= self.best_ask: raise ValueError("order book is crossed")

    @property
    def best_bid(self) -> float:
        return self.bids[0].price

    @property
    def best_ask(self) -> float:
        return self.asks[0].price

    @property
    def mid_price(self) -> float:
        return (self.best_bid + self.best_ask) / 2

    @property
    def spread(self) -> float:
        return self.best_ask - self.best_bid