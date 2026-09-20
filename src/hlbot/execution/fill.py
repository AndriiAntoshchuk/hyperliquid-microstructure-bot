from dataclasses import dataclass
from math import isfinite

from hlbot.models.trade import TradeSide

@dataclass(frozen=True)
class ExecutionFill:
    fill_id: str
    client_order_id: str
    coin: str
    side: TradeSide
    quantity: float
    price: float
    fee: float
    timestamp: float

    def __post_init__(self):
        if not self.fill_id: raise ValueError("fill_id cannot be empty")
        if not self.client_order_id: raise ValueError("client_order_id cannot be empty")
        if not self.coin: raise ValueError("coin cannot be empty")

        for name in ("quantity", "price", "fee", "timestamp"):
            if not isfinite(getattr(self, name)): raise ValueError(f"{name} must be finite")

        if self.quantity <= 0: raise ValueError("quantity must be positive")
        if self.price <= 0: raise ValueError("price must be positive")
        if self.fee < 0: raise ValueError("fee cannot be negative")
        if self.timestamp <= 0: raise ValueError("timestamp must be positive")

    @property
    def notional(self) -> float:
        return self.quantity * self.price

    @property
    def signed_quantity(self) -> float:
        return self.quantity if self.side == TradeSide.BUY else -self.quantity