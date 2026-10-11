from dataclasses import dataclass
from typing import Protocol

from hlbot.strategy.order_intent import OrderIntent

@dataclass(frozen=True)
class ExecutionResult:
    accepted: bool
    order_id: str | None = None
    reason: str = ""

    def __post_init__(self):
        if self.accepted and not self.order_id:
            raise ValueError("accepted execution requires order_id")

        if not self.accepted and self.order_id is not None:
            raise ValueError("rejected execution cannot have order_id")

class ExecutionClient(Protocol):
    def submit(self, intent: OrderIntent) -> ExecutionResult:
        ...