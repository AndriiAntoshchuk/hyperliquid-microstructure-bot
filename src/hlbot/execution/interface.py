from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Protocol

from hlbot.models.trade import TradeSide

class PositionAction(Enum):
    OPEN = "open"
    CLOSE = "close"

@dataclass(frozen=True)
class PlaceOrderRequest:
    coin: str
    side: TradeSide
    action: PositionAction
    notional: float
    price: float | None = None
    post_only: bool = False

    def __post_init__(self):
        if not self.coin: raise ValueError("coin cannot be empty")
        if not isfinite(self.notional) or self.notional <= 0: raise ValueError("notional must be positive and finite")
        if self.price is not None and (not isfinite(self.price) or self.price <= 0): raise ValueError("price must be positive and finite")
        if self.post_only and self.price is None: raise ValueError("post-only order requires price")

    @property
    def reduce_only(self) -> bool:
        return self.action == PositionAction.CLOSE

@dataclass(frozen=True)
class AdapterOrder:
    client_order_id: str
    exchange_order_id: str | None
    coin: str
    side: TradeSide
    action: PositionAction
    status: str

@dataclass(frozen=True)
class AdapterPosition:
    coin: str
    quantity: float
    entry_price: float | None
    unrealized_pnl: float
    leverage: float | None = None

    @property
    def direction(self) -> str:
        if self.quantity > 0: return "long"
        if self.quantity < 0: return "short"
        return "flat"

@dataclass(frozen=True)
class AdapterBalance:
    asset: str
    total: float
    available: float

class ExecutionAdapter(Protocol):
    def place_taker(self, request: PlaceOrderRequest) -> str: ...
    def place_maker(self, request: PlaceOrderRequest) -> str: ...
    def cancel(self, client_order_id: str) -> None: ...
    def replace(self, client_order_id: str, request: PlaceOrderRequest) -> str: ...
    def position(self, coin: str) -> AdapterPosition: ...
    def balances(self) -> tuple[AdapterBalance, ...]: ...
    def active_orders(self) -> tuple[AdapterOrder, ...]: ...