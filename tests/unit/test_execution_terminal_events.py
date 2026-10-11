import pytest

from hlbot.execution.account_tracker import AccountTracker
from hlbot.execution.event_processor import ExecutionEventProcessor
from hlbot.execution.fill import ExecutionFill
from hlbot.execution.latency import ExecutionLatencyTracker, ExecutionStage
from hlbot.execution.order_state import ExecutionOrderState, OrderStatus
from hlbot.execution.order_tracker import OrderTracker
from hlbot.models.trade import TradeSide

def setup(status=OrderStatus.PENDING):
    orders = OrderTracker()
    orders.add(ExecutionOrderState("order-1", status, 100, 100))
    return ExecutionEventProcessor(orders, AccountTracker(10000)), orders

def test_reject_pending_order():
    processor, orders = setup()

    processor.reject("order-1", 101, "exchange rejected")

    order = orders.get("order-1")
    assert order.status == OrderStatus.REJECTED
    assert order.reason == "exchange rejected"
    assert order.terminal

def test_cancel_open_order():
    processor, orders = setup(OrderStatus.OPEN)

    processor.cancel("order-1", 101)

    assert orders.get("order-1").status == OrderStatus.CANCELLED
    assert orders.active_order_count == 0

def test_cancel_partial_fill_preserves_fill():
    orders = OrderTracker()
    orders.add(ExecutionOrderState(
        "order-1",
        OrderStatus.PARTIALLY_FILLED,
        100,
        101,
        "exchange-1",
        2,
        100
    ))
    processor = ExecutionEventProcessor(orders, AccountTracker(10000))

    processor.cancel("order-1", 102)

    order = orders.get("order-1")
    assert order.status == OrderStatus.CANCELLED
    assert order.filled_quantity == 2
    assert order.average_fill_price == 100

def test_open_order_cannot_be_rejected():
    processor, _ = setup(OrderStatus.OPEN)

    with pytest.raises(ValueError):
        processor.reject("order-1", 101)

def test_rejection_records_exchange_response_latency():
    orders = OrderTracker()
    orders.add(ExecutionOrderState("order-1", OrderStatus.PENDING, 100, 100))
    latency = ExecutionLatencyTracker()
    latency.start("trace-1")
    latency.record("trace-1", ExecutionStage.DECISION_CREATED)
    latency.record("trace-1", ExecutionStage.RISK_APPROVED)
    latency.record("trace-1", ExecutionStage.ORDER_SUBMITTED)

    processor = ExecutionEventProcessor(orders, AccountTracker(10000), latency)
    processor.reject("order-1", 101, "rejected", "trace-1")

    assert latency.timestamp_ns("trace-1", ExecutionStage.EXCHANGE_ACKNOWLEDGED) is not None