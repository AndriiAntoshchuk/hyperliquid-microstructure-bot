import pytest

from hlbot.execution.order_state import ExecutionOrderState, OrderStatus
from hlbot.execution.order_tracker import OrderTracker

def state(
    status: OrderStatus = OrderStatus.PENDING,
    client_order_id: str = "client-1",
    **overrides
) -> ExecutionOrderState:
    values = {
        "client_order_id": client_order_id,
        "status": status,
        "submitted_ts": 100,
        "updated_ts": 100
    }
    values.update(overrides)
    return ExecutionOrderState(**values)

def test_add_and_get_order():
    tracker = OrderTracker()
    order = state()

    tracker.add(order)

    assert tracker.get("client-1") == order
    assert len(tracker) == 1

def test_duplicate_order_is_rejected():
    tracker = OrderTracker()
    tracker.add(state())

    with pytest.raises(ValueError):
        tracker.add(state())

def test_unknown_order_is_rejected():
    tracker = OrderTracker()

    with pytest.raises(KeyError):
        tracker.get("missing")

def test_valid_order_update():
    tracker = OrderTracker()
    tracker.add(state())

    updated = state(
        OrderStatus.OPEN,
        updated_ts=101,
        exchange_order_id="exchange-1"
    )
    tracker.update(updated)

    assert tracker.get("client-1") == updated

def test_active_and_terminal_orders():
    tracker = OrderTracker()

    tracker.add(state(client_order_id="open"))
    tracker.add(
        state(
            OrderStatus.FILLED,
            client_order_id="filled",
            updated_ts=101,
            filled_quantity=1,
            average_fill_price=100
        )
    )

    assert len(tracker.active_orders()) == 1
    assert len(tracker.terminal_orders()) == 1
    assert tracker.active_order_count == 1

def test_fill_quantity_cannot_decrease():
    tracker = OrderTracker()

    tracker.add(
        state(
            OrderStatus.PARTIALLY_FILLED,
            filled_quantity=2,
            average_fill_price=100
        )
    )

    with pytest.raises(ValueError):
        tracker.update(
            state(
                OrderStatus.PARTIALLY_FILLED,
                updated_ts=101,
                filled_quantity=1,
                average_fill_price=100
            )
        )

def test_update_timestamp_cannot_move_backwards():
    tracker = OrderTracker()
    tracker.add(state(OrderStatus.OPEN, updated_ts=102))

    with pytest.raises(ValueError):
        tracker.update(state(OrderStatus.OPEN, updated_ts=101))

def test_submitted_timestamp_cannot_change():
    tracker = OrderTracker()
    tracker.add(state())

    with pytest.raises(ValueError):
        tracker.update(
            ExecutionOrderState(
                client_order_id="client-1",
                status=OrderStatus.OPEN,
                submitted_ts=101,
                updated_ts=101
            )
        )

def test_exchange_order_id_cannot_change():
    tracker = OrderTracker()

    tracker.add(
        state(
            OrderStatus.OPEN,
            exchange_order_id="exchange-1"
        )
    )

    with pytest.raises(ValueError):
        tracker.update(
            state(
                OrderStatus.OPEN,
                updated_ts=101,
                exchange_order_id="exchange-2"
            )
        )