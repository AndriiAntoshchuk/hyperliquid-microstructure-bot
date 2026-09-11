from dataclasses import dataclass
from enum import Enum

class TradeSide(str, Enum):
    BUY = "buy"
    SELL = "sell"

@dataclass(frozen=True)
class Trade:
    trade_id: str
    exchange: str
    trading_pair: str
    exchange_ts: float
    local_ts: float
    price: float
    quantity: float
    side: TradeSide

    def __post_init__(self):
        if not self.trade_id:
            raise ValueError("trade_id cannot be empty")

        if not self.exchange:
            raise ValueError("exchange cannot be empty")

        if not self.trading_pair:
            raise ValueError("trading_pair cannot be empty")

        if self.exchange_ts <= 0:
            raise ValueError("exchange_ts must be positive")

        if self.local_ts <= 0:
            raise ValueError("local_ts must be positive")

        if self.price <= 0:
            raise ValueError("price must be positive")

        if self.quantity <= 0:
            raise ValueError("quantity must be positive")