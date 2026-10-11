from dataclasses import replace

from hlbot.execution.account_tracker import AccountTracker
from hlbot.execution.fill import ExecutionFill
from hlbot.execution.latency import ExecutionLatencyTracker, ExecutionStage
from hlbot.execution.order_state import OrderStatus
from hlbot.execution.order_tracker import OrderTracker

class ExecutionEventProcessor:
    def __init__(self, orders: OrderTracker, account: AccountTracker, latency: ExecutionLatencyTracker | None = None):
        self.orders = orders
        self.account = account
        self.latency = latency

    def acknowledge(self, client_order_id: str, exchange_order_id: str, timestamp: float, trace_id: str | None = None) -> None:
        if not exchange_order_id: raise ValueError("exchange_order_id cannot be empty")
        current = self.orders.get(client_order_id)

        if current.status == OrderStatus.PENDING:
            self.orders.update(replace(
                current,
                status=OrderStatus.OPEN,
                updated_ts=max(timestamp, current.updated_ts),
                exchange_order_id=exchange_order_id
            ))
        elif current.status in {OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED}:
            self.orders.update(replace(
                current,
                updated_ts=max(timestamp, current.updated_ts),
                exchange_order_id=exchange_order_id
            ))
        else:
            raise ValueError(f"cannot acknowledge {current.status.value} order")

        self._record(trace_id, ExecutionStage.EXCHANGE_ACKNOWLEDGED)

    def reject(self, client_order_id: str, timestamp: float, reason: str = "", trace_id: str | None = None) -> None:
        current = self.orders.get(client_order_id)
        self.orders.update(replace(
            current,
            status=OrderStatus.REJECTED,
            updated_ts=max(timestamp, current.updated_ts),
            reason=reason
        ))
        self._record(trace_id, ExecutionStage.EXCHANGE_ACKNOWLEDGED)

    def cancel(self, client_order_id: str, timestamp: float, reason: str = "") -> None:
        current = self.orders.get(client_order_id)
        self.orders.update(replace(
            current,
            status=OrderStatus.CANCELLED,
            updated_ts=max(timestamp, current.updated_ts),
            reason=reason
        ))

    def apply_fill(self, fill: ExecutionFill, status: OrderStatus, timestamp: float, exchange_order_id: str | None = None, trace_id: str | None = None) -> None:
        if status not in {OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED}:
            raise ValueError("fill status must be partially_filled or filled")
        if self.account.has_fill(fill.fill_id):
            raise ValueError(f"duplicate fill: {fill.fill_id}")

        current = self.orders.get(fill.client_order_id)
        quantity = current.filled_quantity + fill.quantity
        old_notional = current.filled_quantity * (current.average_fill_price or 0)
        average = (old_notional + fill.quantity * fill.price) / quantity

        updated = replace(
            current,
            status=status,
            updated_ts=max(timestamp, current.updated_ts),
            exchange_order_id=exchange_order_id or current.exchange_order_id,
            filled_quantity=quantity,
            average_fill_price=average
        )

        self.orders.update(updated)
        self.account.apply_fill(fill)

        if current.filled_quantity == 0:
            self._record(trace_id, ExecutionStage.FIRST_FILL)

    def complete(self, client_order_id: str, timestamp: float, exchange_order_id: str | None = None) -> None:
        current = self.orders.get(client_order_id)

        if current.status == OrderStatus.FILLED: return
        if current.filled_quantity <= 0:
            raise ValueError("cannot complete order without fills")

        self.orders.update(replace(
            current,
            status=OrderStatus.FILLED,
            updated_ts=max(timestamp, current.updated_ts),
            exchange_order_id=exchange_order_id or current.exchange_order_id
        ))

    def _record(self, trace_id: str | None, stage: ExecutionStage) -> None:
        if trace_id is None: return
        if self.latency is None: raise ValueError("trace_id requires latency tracker")
        if self.latency.timestamp_ns(trace_id, stage) is not None: return
        self.latency.record(trace_id, stage)
