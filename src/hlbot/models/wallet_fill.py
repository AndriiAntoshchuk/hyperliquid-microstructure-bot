from dataclasses import dataclass

@dataclass(frozen=True)
class WalletFill:
    wallet: str
    coin: str
    timestamp: float
    price: float
    quantity: float
    side: str
    trade_id: str
    direction: str
    order_id: int
    closed_pnl: float
    crossed: bool
    fee: float
    fee_token: str
    transaction_hash: str
    start_position: float | None = None
    client_order_id: str | None = None
    twap_id: int | None = None

    def __post_init__(self):
        if not self.wallet: raise ValueError("wallet cannot be empty")
        if not self.coin: raise ValueError("coin cannot be empty")
        if self.timestamp <= 0: raise ValueError("timestamp must be positive")
        if self.price <= 0: raise ValueError("price must be positive")
        if self.quantity <= 0: raise ValueError("quantity must be positive")
        if self.side not in {"buy", "sell"}: raise ValueError("side must be 'buy' or 'sell'")
        if not self.trade_id: raise ValueError("trade_id cannot be empty")
        if not self.direction: raise ValueError("direction cannot be empty")
        if self.order_id < 0: raise ValueError("order_id cannot be negative")
        if self.fee < 0: raise ValueError("fee cannot be negative")