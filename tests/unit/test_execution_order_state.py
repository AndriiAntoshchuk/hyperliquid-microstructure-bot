import pytest

from hlbot.execution.order_state import ExecutionOrderState, OrderStatus, validate_transition

def state(status: OrderStatus = OrderStatus.PENDING, **overrides) -> ExecutionOrderState:
    values = {
        "client_order_id": "client-1",
        "status": status,
        "submitted_ts": 100,
        "updated_ts": 100
    }
    values.update(overrides)
    return ExecutionOrderState(**values)

def test_pending_order_is_active():
    order = state()
    assert order.active
    assert not order.terminal

def test_filled_order_is_terminal():
    order = state(
        OrderStatus.FILLED,
        updated_ts=101,
        filled_quantity=2,
        average_fill_price=100
    )
    assert order.terminal
    assert not order.active

def test_cancelled_partial_order_is_valid():
    order = state(
        OrderStatus.CANCELLED,
        updated_ts=101,
        filled_quantity=1,
        average_fill_price=100
    )
    assert order.terminal

def test_rejected_order_cannot_have_fill():
    with pytest.raises(ValueError):
        state(
            OrderStatus.REJECTED,
            filled_quantity=1,
            average_fill_price=100
        )

def test_fill_requires_average_price():
    with pytest.raises(ValueError):
        state(
            OrderStatus.PARTIALLY_FILLED,
            filled_quantity=1
        )

def test_average_price_requires_fill():
    with pytest.raises(ValueError):
        state(average_fill_price=100)

def test_valid_transitions():
    validate_transition(OrderStatus.PENDING, OrderStatus.OPEN)
    validate_transition(OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED)
    validate_transition(OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED)

def test_direct_pending_fill_is_valid():
    validate_transition(OrderStatus.PENDING, OrderStatus.FILLED)

def test_terminal_transition_is_invalid():
    with pytest.raises(ValueError):
        validate_transition(OrderStatus.FILLED, OrderStatus.OPEN)

def test_open_to_rejected_is_invalid():
    with pytest.raises(ValueError):
        validate_transition(OrderStatus.OPEN, OrderStatus.REJECTED)