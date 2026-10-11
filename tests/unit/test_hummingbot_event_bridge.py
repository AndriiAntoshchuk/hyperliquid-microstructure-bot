from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from hlbot.execution.event_processor import ExecutionEventProcessor
from hlbot.execution.hummingbot_event_bridge import HummingbotExecutionEventBridge
from hlbot.execution.order_state import ExecutionOrderState, OrderStatus
from hlbot.execution.order_tracker import OrderTracker
from hlbot.models.trade import TradeSide

class DummyAccount:
    def has_fill(self, fill_id: str) -> bool:
        return False

    def apply_fill(self, fill) -> None:
        pass

def test_created_event_acknowledges_order():
    processor = Mock()
    bridge = HummingbotExecutionEventBridge(processor, lambda event: 0.0)
    bridge.bind_trace("cid-1", "trace-1")

    bridge.on_order_created(SimpleNamespace(
        order_id="cid-1",
        exchange_order_id="oid-1",
        timestamp=10.0
    ))

    processor.acknowledge.assert_called_once_with(
        "cid-1",
        "oid-1",
        10.0,
        "trace-1"
    )

def test_failure_rejects_and_releases_trace():
    processor = Mock()
    bridge = HummingbotExecutionEventBridge(processor, lambda event: 0.0)
    bridge.bind_trace("cid-1", "trace-1")

    bridge.on_order_failure(SimpleNamespace(
        order_id="cid-1",
        timestamp=10.0,
        error_message="rejected"
    ))

    processor.reject.assert_called_once_with(
        "cid-1",
        10.0,
        "rejected",
        "trace-1"
    )
    assert bridge.trace_id("cid-1") is None

def test_cancel_releases_trace():
    processor = Mock()
    bridge = HummingbotExecutionEventBridge(processor, lambda event: 0.0)
    bridge.bind_trace("cid-1", "trace-1")

    bridge.on_order_cancelled(SimpleNamespace(
        order_id="cid-1",
        timestamp=10.0
    ))

    processor.cancel.assert_called_once_with("cid-1", 10.0, "")
    assert bridge.trace_id("cid-1") is None

def test_fill_is_translated_to_execution_fill():
    processor = Mock()
    bridge = HummingbotExecutionEventBridge(processor, lambda event: 0.25)
    bridge.bind_trace("cid-1", "trace-1")

    bridge.on_order_filled(SimpleNamespace(
        order_id="cid-1",
        exchange_order_id="oid-1",
        exchange_trade_id="fill-1",
        trading_pair="PONS-USD",
        trade_type=SimpleNamespace(name="BUY"),
        amount=12.0,
        price=0.75,
        timestamp=10.0
    ))

    args = processor.apply_fill.call_args.args
    fill = args[0]

    assert fill.fill_id == "fill-1"
    assert fill.client_order_id == "cid-1"
    assert fill.coin == "PONS"
    assert fill.side == TradeSide.BUY
    assert fill.quantity == 12.0
    assert fill.price == 0.75
    assert fill.fee == 0.25
    assert args[1] == OrderStatus.PARTIALLY_FILLED
    assert args[2] == 10.0
    assert args[3] == "oid-1"
    assert args[4] == "trace-1"

def test_completed_event_marks_order_filled_and_releases_trace():
    processor = Mock()
    bridge = HummingbotExecutionEventBridge(processor, lambda event: 0.0)
    bridge.bind_trace("cid-1", "trace-1")

    bridge.on_order_completed(SimpleNamespace(
        order_id="cid-1",
        exchange_order_id="oid-1",
        timestamp=11.0
    ))

    processor.complete.assert_called_once_with("cid-1", 11.0, "oid-1")
    assert bridge.trace_id("cid-1") is None

def test_trace_cannot_be_rebound_to_different_trace():
    processor = Mock()
    bridge = HummingbotExecutionEventBridge(processor, lambda event: 0.0)

    bridge.bind_trace("cid-1", "trace-1")

    with pytest.raises(ValueError, match="trace already bound"):
        bridge.bind_trace("cid-1", "trace-2")

def test_complete_transitions_partial_order_to_filled():
    orders = OrderTracker()
    orders.add(ExecutionOrderState(
        client_order_id="cid-1",
        status=OrderStatus.PARTIALLY_FILLED,
        submitted_ts=1.0,
        updated_ts=2.0,
        exchange_order_id="oid-1",
        filled_quantity=5.0,
        average_fill_price=10.0
    ))
    processor = ExecutionEventProcessor(orders, DummyAccount())

    processor.complete("cid-1", 3.0, "oid-1")

    order = orders.get("cid-1")
    assert order.status == OrderStatus.FILLED
    assert order.filled_quantity == 5.0
    assert order.average_fill_price == 10.0

def test_complete_requires_at_least_one_fill():
    orders = OrderTracker()
    orders.add(ExecutionOrderState(
        client_order_id="cid-1",
        status=OrderStatus.OPEN,
        submitted_ts=1.0,
        updated_ts=2.0,
        exchange_order_id="oid-1"
    ))
    processor = ExecutionEventProcessor(orders, DummyAccount())

    with pytest.raises(ValueError, match="without fills"):
        processor.complete("cid-1", 3.0, "oid-1")

def test_cancel_event_notifies_replacement_handler():
    processor = Mock()
    replacement = Mock()
    bridge = HummingbotExecutionEventBridge(
        processor,
        lambda event: 0.0,
        replacement_handler=replacement
    )

    bridge.on_order_cancelled(SimpleNamespace(
        order_id="cid-1",
        timestamp=10.0
    ))

    processor.cancel.assert_called_once_with("cid-1", 10.0, "")
    replacement.on_cancelled.assert_called_once_with("cid-1")

def test_fill_event_invalidates_pending_replacement():
    processor = Mock()
    replacement = Mock()
    bridge = HummingbotExecutionEventBridge(
        processor,
        lambda event: 0.0,
        replacement_handler=replacement
    )

    bridge.on_order_filled(SimpleNamespace(
        order_id="cid-1",
        exchange_order_id="oid-1",
        exchange_trade_id="fill-1",
        trading_pair="PONS-USD",
        trade_type=SimpleNamespace(name="BUY"),
        amount=1.0,
        price=10.0,
        timestamp=10.0
    ))

    replacement.invalidate.assert_called_once_with(
        "cid-1",
        "order filled before cancellation confirmation"
    )