from hlbot.execution.order_state import ExecutionOrderState, validate_transition

class OrderTracker:
    def __init__(self):
        self._orders: dict[str, ExecutionOrderState] = {}

    def add(self, order: ExecutionOrderState) -> None:
        if order.client_order_id in self._orders:
            raise ValueError(f"order already exists: {order.client_order_id}")

        self._orders[order.client_order_id] = order

    def update(self, order: ExecutionOrderState) -> None:
        current = self.get(order.client_order_id)

        validate_transition(current.status, order.status)

        if order.submitted_ts != current.submitted_ts:
            raise ValueError("submitted_ts cannot change")

        if order.updated_ts < current.updated_ts:
            raise ValueError("updated_ts cannot move backwards")

        if order.filled_quantity < current.filled_quantity:
            raise ValueError("filled_quantity cannot decrease")

        if current.exchange_order_id is not None:
            if order.exchange_order_id != current.exchange_order_id:
                raise ValueError("exchange_order_id cannot change")

        self._orders[order.client_order_id] = order

    def get(self, client_order_id: str) -> ExecutionOrderState:
        try:
            return self._orders[client_order_id]
        except KeyError:
            raise KeyError(f"unknown order: {client_order_id}") from None

    def all_orders(self) -> tuple[ExecutionOrderState, ...]:
        return tuple(self._orders.values())

    def active_orders(self) -> tuple[ExecutionOrderState, ...]:
        return tuple(order for order in self._orders.values() if order.active)

    def terminal_orders(self) -> tuple[ExecutionOrderState, ...]:
        return tuple(order for order in self._orders.values() if order.terminal)

    @property
    def active_order_count(self) -> int:
        return len(self.active_orders())

    def __len__(self) -> int:
        return len(self._orders)