from dataclasses import dataclass
from enum import Enum

class PositionSide(str, Enum):
    LONG = "long"
    SHORT = "short"

@dataclass(frozen=True)
class WalletFill:
    wallet: str
    coin: str
    timestamp: float
    price: float
    quantity: float
    side: str
    trade_id: str
    order_id: str | None = None
    closed_pnl: float | None = None
    transaction_hash: str | None = None

    def __post_init__(self):
        if not self.wallet:
            raise ValueError("wallet cannot be empty")

        if not self.coin:
            raise ValueError("coin cannot be empty")

        if self.timestamp <= 0:
            raise ValueError("timestamp must be positive")

        if self.price <= 0:
            raise ValueError("price must be positive")

        if self.quantity <= 0:
            raise ValueError("quantity must be positive")

        if self.side not in {"buy", "sell"}:
            raise ValueError("side must be 'buy' or 'sell'")

        if not self.trade_id:
            raise ValueError("trade_id cannot be empty")