from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import Mock

from hlbot.execution.client import ExecutionResult
from hlbot.execution.order_tracker import OrderTracker
from hlbot.execution.risk_checked import RiskCheckedExecutor

@dataclass(frozen=True)
class Context:
    timestamp: float
    open_orders: int = 0

def test_accepted_order_binds_trace():
    risk_engine = Mock()
    risk_engine.evaluate.return_value = SimpleNamespace(approved=True)

    client = Mock()
    client.submit.return_value = ExecutionResult(True, "cid-1")

    binder = Mock()
    latency = Mock()
    tracker = OrderTracker()
    executor = RiskCheckedExecutor(
        risk_engine,
        client,
        tracker,
        latency=latency,
        trace_binder=binder
    )

    executor.submit(object(), Context(10.0), "trace-1")

    binder.assert_called_once_with("cid-1", "trace-1")
    assert tracker.get("cid-1").client_order_id == "cid-1"

def test_order_without_trace_does_not_bind():
    risk_engine = Mock()
    risk_engine.evaluate.return_value = SimpleNamespace(approved=True)

    client = Mock()
    client.submit.return_value = ExecutionResult(True, "cid-1")

    binder = Mock()
    executor = RiskCheckedExecutor(
        risk_engine,
        client,
        OrderTracker(),
        trace_binder=binder
    )

    executor.submit(object(), Context(10.0))

    binder.assert_not_called()

def test_rejected_execution_does_not_bind():
    risk_engine = Mock()
    risk_engine.evaluate.return_value = SimpleNamespace(approved=True)

    client = Mock()
    client.submit.return_value = ExecutionResult(False, reason="submission failed")

    binder = Mock()
    latency = Mock()
    executor = RiskCheckedExecutor(
        risk_engine,
        client,
        OrderTracker(),
        latency=latency,
        trace_binder=binder
    )

    executor.submit(object(), Context(10.0), "trace-1")

    binder.assert_not_called()