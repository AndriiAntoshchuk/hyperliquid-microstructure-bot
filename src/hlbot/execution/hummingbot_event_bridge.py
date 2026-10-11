from collections.abc import Callable
from typing import Any, Protocol

from hlbot.execution.event_processor import ExecutionEventProcessor
from hlbot.execution.fill import ExecutionFill
from hlbot.execution.order_state import OrderStatus
from hlbot.models.trade import TradeSide

class ReplacementEventHandler(Protocol):
    def on_cancelled(self, client_order_id: str): ...
    def invalidate(self, client_order_id: str, reason: str): ...

class HummingbotExecutionEventBridge:
    def __init__(
        self,
        processor: ExecutionEventProcessor,
        fee_resolver: Callable[[Any], float],
        coin_resolver: Callable[[str], str] | None = None,
        replacement_handler: ReplacementEventHandler | None = None
    ):
        self.processor = processor
        self.fee_resolver = fee_resolver
        self.coin_resolver = coin_resolver or self._default_coin_resolver
        self.replacement_handler = replacement_handler
        self._traces: dict[str, str] = {}

    def bind_trace(self, client_order_id: str, trace_id: str) -> None:
        if not client_order_id: raise ValueError("client_order_id cannot be empty")
        if not trace_id: raise ValueError("trace_id cannot be empty")

        current = self._traces.get(client_order_id)
        if current is not None and current != trace_id:
            raise ValueError(f"trace already bound for order: {client_order_id}")

        self._traces[client_order_id] = trace_id

    def trace_id(self, client_order_id: str) -> str | None:
        return self._traces.get(client_order_id)

    def on_order_created(self, event: Any) -> None:
        client_order_id = self._required_text(event, "order_id")
        exchange_order_id = self._required_text(event, "exchange_order_id")

        self.processor.acknowledge(
            client_order_id,
            exchange_order_id,
            self._timestamp(event),
            self.trace_id(client_order_id)
        )

    def on_order_failure(self, event: Any) -> None:
        client_order_id = self._required_text(event, "order_id")
        reason = self._reason(event)

        self._invalidate_replacement(
            client_order_id,
            reason or "order failed before cancellation"
        )

        self.processor.reject(
            client_order_id,
            self._timestamp(event),
            reason,
            self.trace_id(client_order_id)
        )
        self._traces.pop(client_order_id, None)

    def on_order_cancelled(self, event: Any) -> None:
        client_order_id = self._required_text(event, "order_id")

        self.processor.cancel(
            client_order_id,
            self._timestamp(event),
            self._reason(event)
        )

        if self.replacement_handler is not None:
            self.replacement_handler.on_cancelled(client_order_id)

        self._traces.pop(client_order_id, None)

    def on_order_filled(self, event: Any) -> None:
        client_order_id = self._required_text(event, "order_id")
        trading_pair = self._required_text(event, "trading_pair")

        fill = ExecutionFill(
            fill_id=self._fill_id(event),
            client_order_id=client_order_id,
            coin=self.coin_resolver(trading_pair),
            side=self._trade_side(getattr(event, "trade_type")),
            quantity=float(getattr(event, "amount")),
            price=float(getattr(event, "price")),
            fee=float(self.fee_resolver(event)),
            timestamp=self._timestamp(event)
        )

        self.processor.apply_fill(
            fill,
            OrderStatus.PARTIALLY_FILLED,
            fill.timestamp,
            self._optional_text(event, "exchange_order_id"),
            self.trace_id(client_order_id)
        )

        self._invalidate_replacement(
            client_order_id,
            "order filled before cancellation confirmation"
        )

    def on_order_completed(self, event: Any) -> None:
        client_order_id = self._required_text(event, "order_id")

        self.processor.complete(
            client_order_id,
            self._timestamp(event),
            self._optional_text(event, "exchange_order_id")
        )

        self._invalidate_replacement(
            client_order_id,
            "order completed before cancellation confirmation"
        )
        self._traces.pop(client_order_id, None)

    def _invalidate_replacement(self, client_order_id: str, reason: str) -> None:
        if self.replacement_handler is not None:
            self.replacement_handler.invalidate(client_order_id, reason)

    @staticmethod
    def _timestamp(event: Any) -> float:
        timestamp = float(getattr(event, "timestamp"))
        if timestamp <= 0: raise ValueError("event timestamp must be positive")
        return timestamp

    @staticmethod
    def _required_text(event: Any, name: str) -> str:
        value = getattr(event, name, None)
        if value is None or not str(value):
            raise ValueError(f"event {name} cannot be empty")
        return str(value)

    @staticmethod
    def _optional_text(event: Any, name: str) -> str | None:
        value = getattr(event, name, None)
        return None if value is None or not str(value) else str(value)

    @staticmethod
    def _fill_id(event: Any) -> str:
        value = getattr(event, "exchange_trade_id", None)
        if value is None:
            value = getattr(event, "trade_id", None)
        if value is None or not str(value):
            raise ValueError("fill event requires exchange_trade_id")
        return str(value)

    @staticmethod
    def _trade_side(value: Any) -> TradeSide:
        text = str(getattr(value, "name", value)).upper()

        if text == "BUY": return TradeSide.BUY
        if text == "SELL": return TradeSide.SELL
        raise ValueError(f"unsupported Hummingbot trade side: {text}")

    @staticmethod
    def _reason(event: Any) -> str:
        for name in ("reason", "error_message", "message"):
            value = getattr(event, name, None)
            if value: return str(value)
        return ""

    @staticmethod
    def _default_coin_resolver(trading_pair: str) -> str:
        coin = trading_pair.split("-", 1)[0]
        if not coin: raise ValueError(f"invalid trading pair: {trading_pair}")
        return coin