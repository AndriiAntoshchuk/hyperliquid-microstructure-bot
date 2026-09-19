from dataclasses import dataclass
from enum import Enum
from math import isfinite

class OrderStatus(Enum):
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

TERMINAL_STATUSES = {
    OrderStatus.FILLED,
    OrderStatus.REJECTED,
    OrderStatus.CANCELLED
}

ALLOWED_TRANSITIONS = {
    OrderStatus.PENDING: {
        OrderStatus.OPEN,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.REJECTED,
        OrderStatus.CANCELLED
    },
    OrderStatus.OPEN: {
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCELLED
    },
    OrderStatus.PARTIALLY_FILLED: {
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCELLED
    },
    OrderStatus.FILLED: set(),
    OrderStatus.REJECTED: set(),
    OrderStatus.CANCELLED: set()
}

@dataclass(frozen=True)
class ExecutionOrderState:
    client_order_id: str
    status: OrderStatus
    submitted_ts: float
    updated_ts: float
    exchange_order_id: str | None = None
    filled_quantity: float = 0.0
    average_fill_price: float | None = None
    reason: str = ""

    def __post_init__(self):
        if not self.client_order_id: raise ValueError("client_order_id cannot be empty")
        if not isfinite(self.submitted_ts) or self.submitted_ts <= 0:
            raise ValueError("submitted_ts must be positive and finite")
        if not isfinite(self.updated_ts) or self.updated_ts < self.submitted_ts:
            raise ValueError("updated_ts must be finite and >= submitted_ts")
        if not isfinite(self.filled_quantity) or self.filled_quantity < 0:
            raise ValueError("filled_quantity must be non-negative and finite")

        if self.average_fill_price is not None:
            if not isfinite(self.average_fill_price) or self.average_fill_price <= 0:
                raise ValueError("average_fill_price must be positive and finite")

        if self.filled_quantity == 0 and self.average_fill_price is not None:
            raise ValueError("empty fill cannot have average_fill_price")

        if self.filled_quantity > 0 and self.average_fill_price is None:
            raise ValueError("filled order requires average_fill_price")

        if self.status in {OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED} and self.filled_quantity <= 0:
            raise ValueError("filled status requires positive filled_quantity")

        if self.status == OrderStatus.REJECTED and self.filled_quantity != 0:
            raise ValueError("rejected order cannot have fills")

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    @property
    def active(self) -> bool:
        return not self.terminal

def validate_transition(current: OrderStatus, new: OrderStatus) -> None:
    if new == current: return
    if new not in ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"invalid order transition: {current.value} -> {new.value}")