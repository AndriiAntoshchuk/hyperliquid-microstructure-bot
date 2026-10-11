from dataclasses import dataclass
from math import isfinite

from hlbot.execution.interface import PlaceOrderRequest, PositionAction
from hlbot.models.trade import TradeSide
from hlbot.strategy.order_intent import OrderIntent
from hlbot.strategy.signal import SignalDirection

@dataclass(frozen=True)
class PerpetualOrderInstruction:
    coin: str
    direction: SignalDirection
    action: PositionAction
    notional: float
    price: float | None = None
    post_only: bool = False
    reason: str = ""

    def __post_init__(self):
        if not self.coin: raise ValueError("coin cannot be empty")
        if self.direction == SignalDirection.NONE: raise ValueError("direction cannot be NONE")
        if not isfinite(self.notional) or self.notional <= 0:
            raise ValueError("notional must be positive and finite")
        if self.price is not None and (not isfinite(self.price) or self.price <= 0):
            raise ValueError("price must be positive and finite")
        if self.post_only and self.price is None:
            raise ValueError("post-only instruction requires price")
        if not self.post_only and self.price is not None:
            raise ValueError("taker instruction cannot specify price")

    @property
    def side(self) -> TradeSide:
        if self.action == PositionAction.OPEN:
            return TradeSide.BUY if self.direction == SignalDirection.LONG else TradeSide.SELL

        return TradeSide.SELL if self.direction == SignalDirection.LONG else TradeSide.BUY

    @property
    def increases_exposure(self) -> bool:
        return self.action == PositionAction.OPEN

    @property
    def reduce_only(self) -> bool:
        return self.action == PositionAction.CLOSE

    def request(self) -> PlaceOrderRequest:
        return PlaceOrderRequest(
            coin=self.coin,
            side=self.side,
            action=self.action,
            notional=self.notional,
            price=self.price,
            post_only=self.post_only
        )

def entry_instruction(
    coin: str,
    intent: OrderIntent,
    price: float | None = None,
    post_only: bool = False
) -> PerpetualOrderInstruction:
    return PerpetualOrderInstruction(
        coin=coin,
        direction=intent.direction,
        action=PositionAction.OPEN,
        notional=intent.notional,
        price=price,
        post_only=post_only,
        reason=intent.reason
    )

def exit_instruction(
    coin: str,
    direction: SignalDirection,
    notional: float,
    reason: str = "",
    price: float | None = None,
    post_only: bool = False
) -> PerpetualOrderInstruction:
    return PerpetualOrderInstruction(
        coin=coin,
        direction=direction,
        action=PositionAction.CLOSE,
        notional=notional,
        price=price,
        post_only=post_only,
        reason=reason
    )