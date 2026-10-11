import pytest

from hlbot.execution.account_tracker import AccountTracker
from hlbot.execution.event_processor import ExecutionEventProcessor
from hlbot.execution.fill import ExecutionFill
from hlbot.execution.latency import ExecutionLatencyTracker, ExecutionStage
from hlbot.execution.order_state import ExecutionOrderState, OrderStatus
from hlbot.execution.order_tracker import OrderTracker
from hlbot.models.trade import TradeSide

def setup():
    orders = OrderTracker()
    orders.add(ExecutionOrderState("order-1", OrderStatus.PENDING, 100, 100))
    account = AccountTracker(10000)
    return ExecutionEventProcessor(orders, account), orders, account

def fill(fill_id="fill-1", quantity=1, price=100):
    return ExecutionFill(fill_id, "order-1", "TEST", TradeSide.BUY, quantity, price, 0, 101)

def test_acknowledgement_opens_order():
    processor, orders, _ = setup()

    processor.acknowledge("order-1", "exchange-1", 101)

    order = orders.get("order-1")
    assert order.status == OrderStatus.OPEN
    assert order.exchange_order_id == "exchange-1"

def test_partial_fill_updates_order_and_account():
    processor, orders, account = setup()
    processor.acknowledge("order-1", "exchange-1", 101)

    processor.apply_fill(fill(), OrderStatus.PARTIALLY_FILLED, 102)

    order = orders.get("order-1")
    assert order.filled_quantity == 1
    assert order.average_fill_price == 100
    assert account.position("TEST").quantity == 1

def test_multiple_fills_update_average_price():
    processor, orders, _ = setup()

    processor.apply_fill(fill("fill-1", 1, 100), OrderStatus.PARTIALLY_FILLED, 101)
    processor.apply_fill(fill("fill-2", 1, 110), OrderStatus.FILLED, 102)

    order = orders.get("order-1")
    assert order.status == OrderStatus.FILLED
    assert order.filled_quantity == 2
    assert order.average_fill_price == 105

def test_duplicate_fill_is_rejected():
    processor, orders, _ = setup()
    trade = fill()

    processor.apply_fill(trade, OrderStatus.PARTIALLY_FILLED, 101)

    with pytest.raises(ValueError):
        processor.apply_fill(trade, OrderStatus.FILLED, 102)

    assert orders.get("order-1").filled_quantity == 1

def test_invalid_fill_status_is_rejected():
    processor, _, _ = setup()

    with pytest.raises(ValueError):
        processor.apply_fill(fill(), OrderStatus.OPEN, 101)

def test_latency_records_ack_and_first_fill():
    orders = OrderTracker()
    orders.add(ExecutionOrderState("order-1", OrderStatus.PENDING, 100, 100))
    account = AccountTracker(10000)
    latency = ExecutionLatencyTracker()

    latency.start("trace-1")
    latency.record("trace-1", ExecutionStage.DECISION_CREATED)
    latency.record("trace-1", ExecutionStage.RISK_APPROVED)
    latency.record("trace-1", ExecutionStage.ORDER_SUBMITTED)

    processor = ExecutionEventProcessor(orders, account, latency)
    processor.acknowledge("order-1", "exchange-1", 101, "trace-1")
    processor.apply_fill(fill(), OrderStatus.FILLED, 102, trace_id="trace-1")

    assert latency.timestamp_ns("trace-1", ExecutionStage.EXCHANGE_ACKNOWLEDGED) is not None
    assert latency.timestamp_ns("trace-1", ExecutionStage.FIRST_FILL) is not None